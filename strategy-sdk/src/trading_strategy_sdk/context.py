"""Read-only strategy context assembled from already-closed bars."""

from __future__ import annotations

from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Self, cast

from pydantic import ConfigDict, Field, field_serializer, field_validator, model_validator

from trading_strategy_sdk._model import ContractModel as _ContractModel
from trading_strategy_sdk.events import BarClosedEvent, ClosedBar
from trading_strategy_sdk.market import BarSubscription
from trading_strategy_sdk.positions import PositionBook
from trading_strategy_sdk.spec import (
    SynchronizationMode,
    SynchronizationSpec,
    TriggerSpec,
    WarmupRequirement,
)
from trading_strategy_sdk.state import JsonObject, JsonValue, StrategyState


class _ContextModel(_ContractModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)


class EntryBlocker(StrEnum):
    """Deterministic reasons a context cannot produce a new entry."""

    DATA_INCOMPLETE = "data_incomplete"
    WARMUP_INCOMPLETE = "warmup_incomplete"


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
    positions: PositionBook
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

    @field_validator("state", mode="before")
    @classmethod
    def deserialize_state(cls, value: object) -> StrategyState:
        if isinstance(value, StrategyState):
            return value
        if isinstance(value, dict):
            return StrategyState.from_mapping(cast(dict[str, JsonValue], value))
        raise TypeError("state must be StrategyState or a JSON object")

    @field_serializer("state", return_type=JsonObject)
    def serialize_state(self, value: StrategyState) -> JsonObject:
        return value.to_mapping()

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
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
                if bar.close_time > self.event.event_time:
                    raise ValueError("bar after event_time would permit lookahead")
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
            if bar.close_time > self.event.event_time:
                raise ValueError("synchronized bar after event_time would permit lookahead")
            if (
                self.synchronization.mode is SynchronizationMode.EXACT_CLOSE
                and bar.close_time != self.event.bar.close_time
            ):
                raise ValueError(
                    "EXACT_CLOSE requires every snapshot bar to share the event bar close"
                )
            synchronized[key] = bar
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
    def entry_blockers(self) -> tuple[EntryBlocker, ...]:
        """Return explicit entry blockers in stable priority order."""
        blockers: list[EntryBlocker] = []
        if self.missing_subscriptions:
            blockers.append(EntryBlocker.DATA_INCOMPLETE)
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
