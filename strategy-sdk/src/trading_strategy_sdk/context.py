"""Read-only strategy context assembled from already-closed bars."""

from __future__ import annotations

from calendar import monthrange
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Self

from pydantic import ConfigDict, Field, field_validator, model_validator

from trading_strategy_sdk._model import ContractModel as _ContractModel
from trading_strategy_sdk.events import BarClosedEvent, ClosedBar
from trading_strategy_sdk.market import BarSubscription, Timeframe
from trading_strategy_sdk.orders import (
    ManagedExitPlanSnapshot,
    OcoGroupSnapshot,
    OcoPlacementResult,
    OrderPlacementResult,
    OrderType,
    PendingOrder,
    pending_order_basis,
    validate_directional_protection,
    validate_managed_exit_direction,
)
from trading_strategy_sdk.positions import PositionBook, PositionMode
from trading_strategy_sdk.spec import (
    SynchronizationMode,
    SynchronizationSpec,
    TriggerSpec,
    WarmupRequirement,
)
from trading_strategy_sdk.state import StrategyState


class _ContextModel(_ContractModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class EntryBlocker(StrEnum):
    """Deterministic reasons a context cannot produce a new entry."""

    DATA_INCOMPLETE = "data_incomplete"
    DATA_STALE = "data_stale"
    WARMUP_INCOMPLETE = "warmup_incomplete"


def _monthly_close_after(close_time: datetime) -> datetime | None:
    """Return the next same-day calendar-month close, clamped at month end."""
    if close_time.year == datetime.max.year and close_time.month == 12:
        return None
    year = close_time.year + (1 if close_time.month == 12 else 0)
    month = 1 if close_time.month == 12 else close_time.month + 1
    day = min(close_time.day, monthrange(year, month)[1])
    return close_time.replace(year=year, month=month, day=day)


def _is_stale(bar: ClosedBar, boundary: datetime) -> bool:
    if bar.subscription.timeframe is Timeframe.MN1:
        next_close = _monthly_close_after(bar.close_time)
        return next_close is not None and next_close <= boundary
    return boundary - bar.close_time >= timedelta(minutes=bar.subscription.timeframe.minutes)


class BarSeries(_ContextModel):
    """Strictly ordered history for exactly one subscription."""

    subscription: BarSubscription
    bars: Annotated[tuple[ClosedBar, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_series(self) -> Self:
        if any(bar.subscription != self.subscription for bar in self.bars):
            raise ValueError("all bars must match the series subscription")
        close_times = [bar.close_time for bar in self.bars]
        if any(left >= right for left, right in pairwise(close_times)):
            raise ValueError("bar history must be strictly ordered by close_time")
        return self


class StrategyContext(_ContextModel):
    """A finite event snapshot with no data-provider or account access."""

    event: BarClosedEvent
    trigger: TriggerSpec
    synchronization: SynchronizationSpec
    warmup: tuple[WarmupRequirement, ...]
    histories: tuple[BarSeries, ...] = ()
    synchronized_bars: tuple[ClosedBar, ...] = ()
    position_mode: PositionMode
    positions: PositionBook
    pending_orders: tuple[PendingOrder, ...] = ()
    oco_groups: tuple[OcoGroupSnapshot, ...] = ()
    managed_exit_plans: tuple[ManagedExitPlanSnapshot, ...] = ()
    placement_results: tuple[OrderPlacementResult | OcoPlacementResult, ...] = ()
    state: StrategyState

    @field_validator("histories")
    @classmethod
    def order_histories(cls, values: tuple[BarSeries, ...]) -> tuple[BarSeries, ...]:
        return tuple(sorted(values, key=lambda item: item.subscription.key))

    @field_validator("synchronized_bars")
    @classmethod
    def order_snapshot(cls, values: tuple[ClosedBar, ...]) -> tuple[ClosedBar, ...]:
        return tuple(sorted(values, key=lambda item: item.subscription.key))

    @field_validator("warmup")
    @classmethod
    def order_warmup(cls, values: tuple[WarmupRequirement, ...]) -> tuple[WarmupRequirement, ...]:
        return tuple(sorted(values, key=lambda item: item.subscription.key))

    @field_validator("pending_orders")
    @classmethod
    def order_pending_orders(cls, values: tuple[PendingOrder, ...]) -> tuple[PendingOrder, ...]:
        return tuple(sorted(values, key=lambda item: item.order_id))

    @field_validator("oco_groups")
    @classmethod
    def order_oco_groups(cls, values: tuple[OcoGroupSnapshot, ...]) -> tuple[OcoGroupSnapshot, ...]:
        return tuple(sorted(values, key=lambda item: item.oco_group_id))

    @field_validator("managed_exit_plans")
    @classmethod
    def order_managed_exit_plans(
        cls, values: tuple[ManagedExitPlanSnapshot, ...]
    ) -> tuple[ManagedExitPlanSnapshot, ...]:
        return tuple(sorted(values, key=lambda item: item.managed_exit_plan_id))

    @field_validator("placement_results")
    @classmethod
    def order_placement_results(
        cls, values: tuple[OrderPlacementResult | OcoPlacementResult, ...]
    ) -> tuple[OrderPlacementResult | OcoPlacementResult, ...]:
        return tuple(sorted(values, key=lambda item: (item.created_at, item.intent_id)))

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        boundary = self.event.bar.close_time
        required_subscriptions = self.synchronization.required_subscriptions
        required = {subscription.key: subscription for subscription in required_subscriptions}
        if self.event.bar.subscription.key not in required:
            raise ValueError("event subscription must be required by the context")

        trigger_keys = {subscription.key for subscription in self.trigger.subscriptions}
        if not trigger_keys <= set(required):
            raise ValueError("trigger references a subscription outside synchronization")
        if self.event.bar.subscription.key not in trigger_keys:
            raise ValueError("event subscription must belong to the active trigger")

        warmup_keys = [requirement.subscription.key for requirement in self.warmup]
        if len(set(warmup_keys)) != len(warmup_keys):
            raise ValueError("warmup requirements must be unique by subscription")
        if set(warmup_keys) != set(required):
            raise ValueError("warmup must cover every synchronized subscription")

        history_by_subscription: dict[tuple[str, int], BarSeries] = {}
        for series in self.histories:
            key = series.subscription.key
            if key in history_by_subscription:
                raise ValueError("histories must contain at most one series per subscription")
            if key not in required:
                raise ValueError("history contains an unrequired subscription")
            for bar in series.bars:
                if bar.close_time > boundary:
                    raise ValueError("bar after the event bar close would permit lookahead")
            history_by_subscription[key] = series

        event_history = history_by_subscription.get(self.event.bar.subscription.key)
        if event_history is None or self.event.bar not in event_history.bars:
            raise ValueError("event bar must be materialized in context history")

        synchronized: dict[tuple[str, int], ClosedBar] = {}
        for bar in self.synchronized_bars:
            subscription = bar.subscription
            key = subscription.key
            if key in synchronized:
                raise ValueError("synchronized snapshot contains a duplicate subscription")
            if key not in required:
                raise ValueError("synchronized snapshot contains an unrequired subscription")
            series = history_by_subscription.get(key)
            if series is None or bar != series.bars[-1]:
                raise ValueError("synchronized bar must be the latest materialized bar")
            if bar.close_time > boundary:
                raise ValueError(
                    "synchronized bar after the event bar close would permit lookahead"
                )
            if (
                self.synchronization.mode is SynchronizationMode.EXACT_CLOSE
                and bar.close_time != self.event.bar.close_time
            ):
                raise ValueError(
                    "EXACT_CLOSE requires every snapshot bar to share the event bar close"
                )
            synchronized[key] = bar

        if self.positions.mode is not self.position_mode:
            raise ValueError("position book mode must match the declared position mode")
        allowed_symbols = {subscription.symbol for subscription in required_subscriptions}
        for position in self.positions.positions:
            if position.opened_at > boundary:
                raise ValueError("future position opened after the event bar close")
            if position.symbol not in allowed_symbols:
                raise ValueError("position is outside strategy symbol scope")

        pending_by_id: dict[str, PendingOrder] = {}
        for order in self.pending_orders:
            if order.order_id in pending_by_id:
                raise ValueError("pending order_id values must be unique")
            if order.placed_at > boundary:
                raise ValueError("pending order snapshot is after the event bar close")
            if order.symbol not in allowed_symbols:
                raise ValueError("pending order is outside strategy symbol scope")
            pending_by_id[order.order_id] = order

        groups_by_id: dict[str, OcoGroupSnapshot] = {}
        grouped_order_ids: set[str] = set()
        for group in self.oco_groups:
            if group.oco_group_id in groups_by_id:
                raise ValueError("OCO snapshot identifiers must be unique")
            if group.created_at > boundary:
                raise ValueError("OCO snapshot is after the event bar close")
            for leg in group.legs:
                order = pending_by_id.get(leg.order_id)
                if order is None:
                    raise ValueError("OCO snapshot leg must reference a visible pending order")
                if order.oco_group_id != group.oco_group_id:
                    raise ValueError("OCO snapshot and pending order references must agree")
                if leg.managed_exit_plan_id != order.managed_exit_plan_id:
                    raise ValueError("OCO leg and pending order managed plan references must agree")
                if leg.order_id in grouped_order_ids:
                    raise ValueError("a pending order cannot belong to multiple OCO groups")
                grouped_order_ids.add(leg.order_id)
            groups_by_id[group.oco_group_id] = group
        for order in self.pending_orders:
            if order.oco_group_id is not None:
                group = groups_by_id.get(order.oco_group_id)
                if group is None or order.order_id not in {leg.order_id for leg in group.legs}:
                    raise ValueError("pending order must reference a visible OCO snapshot leg")

        positions_by_id = {position.position_id: position for position in self.positions.positions}
        plans_by_id: dict[str, ManagedExitPlanSnapshot] = {}
        managed_targets: set[tuple[str, str]] = set()
        for plan in self.managed_exit_plans:
            if plan.managed_exit_plan_id in plans_by_id:
                raise ValueError("managed exit plan identifiers must be unique")
            if plan.created_at > boundary:
                raise ValueError("managed exit plan snapshot is after the event bar close")
            if plan.position_id is not None and plan.position_id not in positions_by_id:
                raise ValueError("managed exit plan must reference a visible position")
            if plan.order_id is not None and plan.order_id not in pending_by_id:
                raise ValueError("managed exit plan must reference a visible pending order")
            if plan.position_id is not None:
                target = ("position", plan.position_id)
            else:
                assert plan.order_id is not None
                target = ("order", plan.order_id)
            if target in managed_targets:
                raise ValueError("a target cannot have multiple managed exit plans")
            managed_targets.add(target)
            if plan.order_id is not None:
                order = pending_by_id[plan.order_id]
                if order.managed_exit_plan_id != plan.managed_exit_plan_id:
                    raise ValueError("managed exit plan and pending order references must agree")
                if plan.managed_exit.bracket is not None and (
                    order.stop_loss is not None or order.take_profit is not None
                ):
                    raise ValueError(
                        "native pending-order protection cannot duplicate a managed bracket"
                    )
                order_basis = pending_order_basis(
                    order.order_type, order.entry_price, order.stop_limit_price
                )
                if plan.managed_exit.bracket is not None:
                    validate_directional_protection(
                        order.order_type,
                        order_basis,
                        plan.managed_exit.bracket.stop_loss,
                        plan.managed_exit.bracket.take_profit,
                        label="managed pending-order bracket",
                    )
                validate_managed_exit_direction(
                    is_buy=order.order_type.is_buy,
                    basis=order_basis,
                    managed_exit=plan.managed_exit,
                    label="managed pending-order plan",
                )
            else:
                assert plan.position_id is not None
                position = positions_by_id[plan.position_id]
                is_buy = position.side.value == 0
                if plan.managed_exit.bracket is not None and (
                    position.stop_loss is not None or position.take_profit is not None
                ):
                    raise ValueError(
                        "native position protection cannot duplicate a managed bracket"
                    )
                if position.stop_loss is None and plan.managed_exit.bracket is None:
                    raise ValueError("position must retain native or managed bounded protection")
                visible_bars = [
                    series.bars[-1]
                    for series in self.histories
                    if series.subscription.symbol is position.symbol
                ]
                protection_basis = None
                if visible_bars:
                    latest = max(
                        visible_bars,
                        key=lambda item: (item.close_time, item.subscription.key),
                    )
                    protection_basis = latest.bid.close if is_buy else latest.ask.close
                if plan.managed_exit.bracket is not None:
                    validate_directional_protection(
                        OrderType.BUY if is_buy else OrderType.SELL,
                        protection_basis or position.average_price,
                        plan.managed_exit.bracket.stop_loss,
                        None,
                        label="managed position bracket",
                    )
                    validate_directional_protection(
                        OrderType.BUY if is_buy else OrderType.SELL,
                        position.average_price,
                        None,
                        plan.managed_exit.bracket.take_profit,
                        label="managed position bracket",
                    )
                validate_managed_exit_direction(
                    is_buy=is_buy,
                    basis=position.average_price,
                    managed_exit=plan.managed_exit,
                    label="managed position plan",
                    immediate_trailing_basis=protection_basis,
                )
            plans_by_id[plan.managed_exit_plan_id] = plan
        for position in self.positions.positions:
            if position.stop_loss is None:
                managed_plan = next(
                    (
                        plan
                        for plan in self.managed_exit_plans
                        if plan.position_id == position.position_id
                    ),
                    None,
                )
                if managed_plan is None or managed_plan.managed_exit.bracket is None:
                    raise ValueError("position without a native stop requires a managed bracket")
        for order in self.pending_orders:
            if order.managed_exit_plan_id is not None:
                plan = plans_by_id.get(order.managed_exit_plan_id)
                if plan is None or plan.order_id != order.order_id:
                    raise ValueError("pending order and managed exit plan references must agree")
                if order.stop_loss is None and plan.managed_exit.bracket is None:
                    raise ValueError(
                        "pending order without a native stop requires a managed bracket"
                    )

        result_ids: set[str] = set()
        issued_order_ids: set[str] = set()
        issued_plan_ids: set[str] = set()
        issued_oco_ids: set[str] = set()
        for result in self.placement_results:
            if result.intent_id in result_ids:
                raise ValueError("placement result intent_id values must be unique")
            if result.created_at > boundary:
                raise ValueError("placement result is after the event bar close")
            if isinstance(result, OrderPlacementResult):
                order_ids = (result.order_id,)
                plan_ids = (
                    (result.managed_exit_plan_id,)
                    if result.managed_exit_plan_id is not None
                    else ()
                )
                oco_ids: tuple[str, ...] = ()
            else:
                order_ids = tuple(leg.order_id for leg in result.legs)
                plan_ids = tuple(
                    leg.managed_exit_plan_id
                    for leg in result.legs
                    if leg.managed_exit_plan_id is not None
                )
                oco_ids = (result.oco_group_id,)
            if issued_order_ids.intersection(order_ids):
                raise ValueError("placement result order IDs must be globally unique")
            if issued_plan_ids.intersection(plan_ids):
                raise ValueError("placement result managed plan IDs must be globally unique")
            if issued_oco_ids.intersection(oco_ids):
                raise ValueError("placement result OCO IDs must be globally unique")
            issued_order_ids.update(order_ids)
            issued_plan_ids.update(plan_ids)
            issued_oco_ids.update(oco_ids)
            result_ids.add(result.intent_id)
        return self

    @property
    def required_subscriptions(self) -> tuple[BarSubscription, ...]:
        """Return subscriptions participating in the synchronized entry gate."""
        return self.synchronization.required_subscriptions

    @property
    def missing_subscriptions(self) -> tuple[BarSubscription, ...]:
        """Return feeds absent from the synchronized snapshot in stable order."""
        present = {bar.subscription.key for bar in self.synchronized_bars}
        return tuple(
            sorted(
                (item for item in self.required_subscriptions if item.key not in present),
                key=lambda item: item.key,
            )
        )

    @property
    def warmup_incomplete_subscriptions(self) -> tuple[BarSubscription, ...]:
        """Return subscriptions whose visible history is shorter than declared warmup."""
        history_counts = {series.subscription.key: len(series.bars) for series in self.histories}
        incomplete = (
            requirement.subscription
            for requirement in self.warmup
            if history_counts.get(requirement.subscription.key, 0) < requirement.bars
        )
        return tuple(sorted(incomplete, key=lambda item: item.key))

    @property
    def stale_subscriptions(self) -> tuple[BarSubscription, ...]:
        """Return LATEST_CLOSED feeds old enough that a newer bar should exist."""
        if self.synchronization.mode is not SynchronizationMode.LATEST_CLOSED:
            return ()
        boundary = self.event.bar.close_time
        stale = (bar.subscription for bar in self.synchronized_bars if _is_stale(bar, boundary))
        return tuple(sorted(stale, key=lambda item: item.key))

    @property
    def entry_blockers(self) -> tuple[EntryBlocker, ...]:
        """Return explicit entry blockers in stable priority order."""
        blockers: list[EntryBlocker] = []
        if self.missing_subscriptions:
            blockers.append(EntryBlocker.DATA_INCOMPLETE)
        if self.stale_subscriptions:
            blockers.append(EntryBlocker.DATA_STALE)
        if self.warmup_incomplete_subscriptions:
            blockers.append(EntryBlocker.WARMUP_INCOMPLETE)
        return tuple(blockers)

    @property
    def entries_allowed(self) -> bool:
        """Whether this snapshot is complete enough for a new entry."""
        return not self.entry_blockers

    @property
    def protective_exits_allowed(self) -> bool:
        """Protective actions remain eligible even when entry data is incomplete."""
        return True

    def history(self, subscription: BarSubscription) -> tuple[ClosedBar, ...]:
        """Return only the finite, pre-materialized history for a subscription."""
        for series in self.histories:
            if series.subscription == subscription:
                return series.bars
        return ()

    def latest_bar(self, subscription: BarSubscription) -> ClosedBar | None:
        """Return the latest visible closed bar, if supplied."""
        bars = self.history(subscription)
        return bars[-1] if bars else None
