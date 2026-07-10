"""Closed strategy output and spec/context-aware semantic validation."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Self, cast

from pydantic import Field, ValidationError, field_validator, model_validator

from trading_strategy_sdk._model import ContractModel
from trading_strategy_sdk.context import StrategyContext
from trading_strategy_sdk.events import ClosedBar
from trading_strategy_sdk.intents import (
    CancelOcoIntent,
    CancelOrderIntent,
    ClearManagedExitIntent,
    CloseByIntent,
    ClosePositionIntent,
    ModifyManagedExitIntent,
    ModifyOcoIntent,
    ModifyOrderIntent,
    OrderIntent,
    PlaceOcoIntent,
    PlaceOrderIntent,
    ProtectPositionIntent,
    SignalIntent,
)
from trading_strategy_sdk.market import Symbol
from trading_strategy_sdk.orders import (
    ManagedExitPlan,
    ManagedExitPlanSnapshot,
    OcoGroup,
    OcoGroupSnapshot,
    OrderFilling,
    OrderType,
    PendingOrder,
    pending_order_basis,
    validate_directional_protection,
    validate_managed_exit_direction,
    validate_pending_filling,
)
from trading_strategy_sdk.positions import Position, PositionMode, PositionSide
from trading_strategy_sdk.spec import Capability, StrategySpec
from trading_strategy_sdk.state import StrategyState

_MAX_OUTPUT_ITEMS = 256


class StrategyOutput(ContractModel):
    """One finite strategy decision with explicit next state."""

    signals: Annotated[tuple[SignalIntent, ...], Field(max_length=_MAX_OUTPUT_ITEMS)] = ()
    intents: Annotated[tuple[OrderIntent, ...], Field(max_length=_MAX_OUTPUT_ITEMS)] = ()
    next_state: StrategyState

    @field_validator("signals", "intents", mode="before")
    @classmethod
    def bound_collection_input(cls, value: object) -> object:
        if type(value) not in {list, tuple}:
            raise ValueError("strategy output collections must be finite sequences")
        sequence = cast(list[object] | tuple[object, ...], value)
        if len(sequence) > _MAX_OUTPUT_ITEMS:
            raise ValueError("strategy output collection exceeds the item limit")
        return sequence

    @model_validator(mode="after")
    def identifiers_are_unique(self) -> Self:
        signal_ids = [signal.signal_id for signal in self.signals]
        if len(set(signal_ids)) != len(signal_ids):
            raise ValueError("signal_id values must be unique")
        intent_ids = [intent.intent_id for intent in self.intents]
        if len(set(intent_ids)) != len(intent_ids):
            raise ValueError("intent_id values must be unique")
        return self


def _visible_symbol_bars(context: StrategyContext, symbol: Symbol) -> tuple[ClosedBar, ...]:
    synchronized = tuple(
        bar for bar in context.synchronized_bars if bar.subscription.symbol is symbol
    )
    history_tails = tuple(
        series.bars[-1] for series in context.histories if series.subscription.symbol is symbol
    )
    return (*synchronized, *history_tails)


def _latest_symbol_basis(context: StrategyContext, symbol: Symbol, *, is_buy: bool) -> Decimal:
    candidates = _visible_symbol_bars(context, symbol)
    if not candidates:
        raise ValueError(f"no closed-bar basis is visible for {symbol.value}")
    bar = max(candidates, key=lambda item: (item.close_time, item.subscription.key))
    return bar.ask.close if is_buy else bar.bid.close


def _latest_protection_basis(
    context: StrategyContext, symbol: Symbol, *, is_buy: bool
) -> Decimal | None:
    candidates = _visible_symbol_bars(context, symbol)
    if not candidates:
        return None
    bar = max(candidates, key=lambda item: (item.close_time, item.subscription.key))
    return bar.bid.close if is_buy else bar.ask.close


def _validate_pending_quote_boundary(
    *,
    order_type: OrderType,
    trigger_price: Decimal,
    context: StrategyContext,
    symbol: Symbol,
    label: str,
) -> None:
    """Validate pending placement against the side-correct visible Bid or Ask."""
    current_quote = _latest_symbol_basis(context, symbol, is_buy=order_type.is_buy)
    if order_type in {OrderType.BUY_LIMIT, OrderType.SELL_STOP, OrderType.SELL_STOP_LIMIT}:
        if trigger_price > current_quote:
            side = "Ask" if order_type.is_buy else "Bid"
            raise ValueError(f"{label} must be at or below the current {side}")
    elif (
        order_type in {OrderType.SELL_LIMIT, OrderType.BUY_STOP, OrderType.BUY_STOP_LIMIT}
        and trigger_price < current_quote
    ):
        side = "Ask" if order_type.is_buy else "Bid"
        raise ValueError(f"{label} must be at or above the current {side}")


def _required_managed_capabilities(managed_exit: ManagedExitPlan) -> set[Capability]:
    required: set[Capability] = set()
    if managed_exit.bracket is not None:
        required.add(Capability.PLATFORM_BRACKETS)
    if managed_exit.trailing_stop is not None:
        required.add(Capability.PLATFORM_TRAILING_STOP)
    if managed_exit.break_even is not None:
        required.add(Capability.PLATFORM_BREAK_EVEN)
    if managed_exit.partials:
        required.add(Capability.PLATFORM_PARTIAL_EXITS)
    return required


def _validate_managed_capabilities(
    managed_exit: ManagedExitPlan | None,
    spec: StrategySpec,
) -> None:
    if managed_exit is None:
        return
    missing = _required_managed_capabilities(managed_exit) - set(spec.required_capabilities)
    if missing:
        names = ", ".join(sorted(capability.name for capability in missing))
        raise ValueError(f"managed exit requires declared capabilities: {names}")


def _has_executable_declared_filling(order_type: OrderType, spec: StrategySpec) -> bool:
    for filling in spec.filling_policies:
        if order_type.is_market:
            if filling is not OrderFilling.BOC:
                return True
            continue
        if order_type.is_pending:
            try:
                validate_pending_filling(order_type, filling)
            except ValueError:
                continue
            return True
    return False


def _validate_managed_relationships(
    managed_exit: ManagedExitPlan | None,
    *,
    is_buy: bool,
    basis: Decimal,
    label: str,
    protection_basis: Decimal | None = None,
    validate_bracket: bool = True,
) -> None:
    if managed_exit is None:
        return
    if managed_exit.bracket is not None and validate_bracket:
        validate_directional_protection(
            OrderType.BUY if is_buy else OrderType.SELL,
            protection_basis if protection_basis is not None else basis,
            managed_exit.bracket.stop_loss,
            None,
            label=f"{label} bracket",
        )
        validate_directional_protection(
            OrderType.BUY if is_buy else OrderType.SELL,
            basis,
            None,
            managed_exit.bracket.take_profit,
            label=f"{label} bracket",
        )
    validate_managed_exit_direction(
        is_buy=is_buy,
        basis=basis,
        managed_exit=managed_exit,
        label=label,
        immediate_trailing_basis=protection_basis,
    )


def _validate_group(group: OcoGroup, spec: StrategySpec, context: StrategyContext) -> None:
    declared_symbols = set(spec.symbols)
    for leg in group.legs:
        if leg.symbol not in declared_symbols:
            raise ValueError("OCO leg symbol is not declared by the strategy spec")
        if leg.order_type not in spec.order_types:
            raise ValueError("OCO leg order type is not declared by the strategy spec")
        if leg.filling not in spec.filling_policies:
            raise ValueError("OCO leg filling is not declared by the strategy spec")
        _validate_pending_quote_boundary(
            order_type=leg.order_type,
            trigger_price=leg.entry_price,
            context=context,
            symbol=leg.symbol,
            label="OCO pending trigger",
        )
        _validate_managed_capabilities(leg.managed_exit, spec)
        if leg.managed_exit is not None:
            basis = pending_order_basis(leg.order_type, leg.entry_price, leg.stop_limit_price)
            _validate_managed_relationships(
                leg.managed_exit,
                is_buy=leg.order_type.is_buy,
                basis=basis,
                label="OCO managed exit",
            )
        if (
            leg.bracket is not None
            and Capability.PLATFORM_BRACKETS not in spec.required_capabilities
        ):
            raise ValueError("OCO bracket requires the PLATFORM_BRACKETS capability")


def _position_by_id(context: StrategyContext, position_id: str) -> Position:
    for position in context.positions.positions:
        if position.position_id == position_id:
            return position
    raise ValueError("intent target position is not visible in the strategy context")


def _pending_by_id(context: StrategyContext, order_id: str) -> PendingOrder:
    for order in context.pending_orders:
        if order.order_id == order_id:
            return order
    raise ValueError("intent target pending order is not visible in the strategy context")


def _plan_by_id(context: StrategyContext, managed_exit_plan_id: str) -> ManagedExitPlanSnapshot:
    for plan in context.managed_exit_plans:
        if plan.managed_exit_plan_id == managed_exit_plan_id:
            return plan
    raise ValueError("intent target managed exit plan is not visible in the strategy context")


def _plan_target(
    context: StrategyContext, snapshot: ManagedExitPlanSnapshot
) -> Position | PendingOrder:
    if snapshot.position_id is not None:
        return _position_by_id(context, snapshot.position_id)
    return _pending_by_id(context, cast(str, snapshot.order_id))


def _target_side_and_basis(target: Position | PendingOrder) -> tuple[bool, Decimal]:
    if isinstance(target, Position):
        return (target.side.value == 0, target.average_price)
    return (
        target.order_type.is_buy,
        pending_order_basis(target.order_type, target.entry_price, target.stop_limit_price),
    )


def _target_has_native_stop(target: Position | PendingOrder) -> bool:
    return target.stop_loss is not None


def _oco_by_id(context: StrategyContext, oco_group_id: str) -> OcoGroupSnapshot:
    for group in context.oco_groups:
        if group.oco_group_id == oco_group_id:
            return group
    raise ValueError("intent target OCO group is not visible")


def _validate_lifecycle_collisions(
    intents: tuple[OrderIntent, ...], context: StrategyContext
) -> None:
    reserved: set[tuple[str, str]] = set()

    def reserve(kind: str, identifier: str) -> None:
        target = (kind, identifier)
        if target in reserved:
            raise ValueError("one strategy output cannot mutate a lifecycle target twice")
        reserved.add(target)

    for intent in intents:
        if isinstance(intent, (ModifyOrderIntent, CancelOrderIntent)):
            reserve("order", intent.order_id)
        elif isinstance(intent, (ProtectPositionIntent, ClosePositionIntent)):
            reserve("position", intent.position_id)
        elif isinstance(intent, CloseByIntent):
            reserve("position", intent.position_id)
            reserve("position", intent.opposite_position_id)
        elif isinstance(intent, (ModifyOcoIntent, CancelOcoIntent)):
            group = _oco_by_id(context, intent.oco_group_id)
            reserve("oco", intent.oco_group_id)
            for leg in group.legs:
                reserve("order", leg.order_id)
        elif isinstance(intent, (ModifyManagedExitIntent, ClearManagedExitIntent)):
            plan = _plan_by_id(context, intent.managed_exit_plan_id)
            reserve("managed_exit_plan", intent.managed_exit_plan_id)
            if plan.position_id is not None:
                reserve("position", plan.position_id)
            else:
                reserve("order", cast(str, plan.order_id))


def _revalidate_order_modification(
    intent: ModifyOrderIntent,
    snapshot: PendingOrder,
) -> PendingOrder:
    values = snapshot.model_dump(round_trip=True)
    for field_name in (
        "entry_price",
        "stop_limit_price",
        "stop_loss",
        "take_profit",
        "time",
        "expires_at",
    ):
        value = getattr(intent, field_name)
        if value is not None:
            values[field_name] = value
    if intent.clear_take_profit:
        values["take_profit"] = None
    if intent.clear_expiration:
        values["expires_at"] = None
    try:
        return PendingOrder.model_validate(values)
    except ValidationError as error:
        raise ValueError("modified pending order is not semantically valid") from error


class _ContextualOutput(ContractModel):
    output: StrategyOutput
    spec: StrategySpec
    context: StrategyContext

    @model_validator(mode="after")
    def validate_semantics(self) -> Self:
        spec = self.spec
        context = self.context
        output = self.output

        if context.position_mode is not spec.position_mode:
            raise ValueError("context position mode must match the immutable strategy spec")
        if context.synchronization != spec.synchronization:
            raise ValueError("context synchronization must match the strategy spec")
        if context.trigger not in spec.triggers:
            raise ValueError("context trigger must be declared by the strategy spec")
        if set(context.required_subscriptions) != set(spec.subscriptions):
            raise ValueError("context subscriptions must match the strategy spec")
        if context.warmup != spec.warmup:
            raise ValueError("context warmup requirements must match the strategy spec")
        if context.oco_groups and Capability.PLATFORM_OCO not in spec.required_capabilities:
            raise ValueError("context OCO snapshots require the PLATFORM_OCO capability")
        for order in context.pending_orders:
            if order.order_type not in spec.order_types:
                raise ValueError("context pending order type is not declared by the strategy spec")
            if order.filling not in spec.filling_policies:
                raise ValueError("context pending filling is not declared by the strategy spec")
        for plan in context.managed_exit_plans:
            _validate_managed_capabilities(plan.managed_exit, spec)

        _validate_lifecycle_collisions(output.intents, context)

        has_entry = bool(output.signals) or any(
            isinstance(intent, (PlaceOrderIntent, PlaceOcoIntent)) for intent in output.intents
        )
        if has_entry and context.entry_blockers:
            blockers = ", ".join(blocker.value for blocker in context.entry_blockers)
            raise ValueError(f"new entries are blocked by context entry blockers: {blockers}")

        declared_symbols = set(spec.symbols)
        entry_rules = {rule.name for rule in spec.entries}
        for signal in output.signals:
            if signal.symbol not in declared_symbols:
                raise ValueError("signal symbol is not declared by the strategy spec")
            if signal.rule_name not in entry_rules:
                raise ValueError("signal rule_name is not a declared entry rule")
            is_buy_signal = signal.side is PositionSide.BUY
            if not any(
                order_type is not OrderType.CLOSE_BY
                and order_type.is_buy is is_buy_signal
                and _has_executable_declared_filling(order_type, spec)
                for order_type in spec.order_types
            ):
                raise ValueError("signal side has no executable declared order and filling pair")

        for intent in output.intents:
            if isinstance(intent, PlaceOrderIntent):
                if intent.symbol not in declared_symbols:
                    raise ValueError("order symbol is not declared by the strategy spec")
                if intent.order_type not in spec.order_types:
                    raise ValueError("order type is not declared by the strategy spec")
                if intent.filling not in spec.filling_policies:
                    raise ValueError("order filling is not declared by the strategy spec")
                _validate_managed_capabilities(intent.managed_exit, spec)
                if intent.order_type.is_market:
                    basis = _latest_symbol_basis(
                        context, intent.symbol, is_buy=intent.order_type.is_buy
                    )
                    protection_basis = _latest_protection_basis(
                        context, intent.symbol, is_buy=intent.order_type.is_buy
                    )
                    if protection_basis is None:
                        raise ValueError("market entry requires a visible protection basis")
                    bracket = (
                        intent.managed_exit.bracket if intent.managed_exit is not None else None
                    )
                    stop_loss = bracket.stop_loss if bracket is not None else intent.stop_loss
                    take_profit = bracket.take_profit if bracket is not None else intent.take_profit
                    validate_directional_protection(
                        intent.order_type,
                        protection_basis,
                        stop_loss,
                        None,
                        label="market entry",
                    )
                    validate_directional_protection(
                        intent.order_type,
                        basis,
                        None,
                        take_profit,
                        label="market entry",
                    )
                    _validate_managed_relationships(
                        intent.managed_exit,
                        is_buy=intent.order_type.is_buy,
                        basis=basis,
                        label="market managed exit",
                        protection_basis=protection_basis,
                    )
                else:
                    basis = pending_order_basis(
                        intent.order_type,
                        cast(Decimal, intent.entry_price),
                        intent.stop_limit_price,
                    )
                    _validate_pending_quote_boundary(
                        order_type=intent.order_type,
                        trigger_price=cast(Decimal, intent.entry_price),
                        context=context,
                        symbol=intent.symbol,
                        label="pending entry trigger",
                    )
                    _validate_managed_relationships(
                        intent.managed_exit,
                        is_buy=intent.order_type.is_buy,
                        basis=basis,
                        label="pending managed exit",
                    )
            elif isinstance(intent, PlaceOcoIntent):
                if Capability.PLATFORM_OCO not in spec.required_capabilities:
                    raise ValueError("OCO placement requires the PLATFORM_OCO capability")
                _validate_group(intent.group, spec, context)
            elif isinstance(intent, ModifyOrderIntent):
                snapshot = _pending_by_id(context, intent.order_id)
                if snapshot.order_type not in spec.order_types:
                    raise ValueError("target order type is not declared by the strategy spec")
                if snapshot.filling not in spec.filling_policies:
                    raise ValueError("target order filling is not declared by the strategy spec")
                modified = _revalidate_order_modification(intent, snapshot)
                _validate_pending_quote_boundary(
                    order_type=modified.order_type,
                    trigger_price=modified.entry_price,
                    context=context,
                    symbol=modified.symbol,
                    label="modified pending trigger",
                )
                if snapshot.managed_exit_plan_id is not None:
                    plan_snapshot = _plan_by_id(context, snapshot.managed_exit_plan_id)
                    managed_exit = plan_snapshot.managed_exit
                    if managed_exit.bracket is not None and (
                        modified.stop_loss is not None or modified.take_profit is not None
                    ):
                        raise ValueError(
                            "native pending-order protection cannot duplicate a managed bracket"
                        )
                    basis = pending_order_basis(
                        modified.order_type,
                        modified.entry_price,
                        modified.stop_limit_price,
                    )
                    _validate_managed_relationships(
                        managed_exit,
                        is_buy=modified.order_type.is_buy,
                        basis=basis,
                        label="modified pending-order managed plan",
                    )
            elif isinstance(intent, CancelOrderIntent):
                _pending_by_id(context, intent.order_id)
            elif isinstance(intent, ProtectPositionIntent):
                position = _position_by_id(context, intent.position_id)
                is_buy = position.side.value == 0
                protection_basis = _latest_protection_basis(context, position.symbol, is_buy=is_buy)
                existing_plan = next(
                    (
                        plan
                        for plan in context.managed_exit_plans
                        if plan.position_id == position.position_id
                    ),
                    None,
                )
                _validate_managed_capabilities(intent.managed_exit, spec)
                if intent.managed_exit is not None and existing_plan is not None:
                    raise ValueError("position already has a managed exit plan")
                if (
                    intent.managed_exit is not None
                    and intent.managed_exit.bracket is not None
                    and (position.stop_loss is not None or position.take_profit is not None)
                ):
                    raise ValueError(
                        "managed bracket cannot duplicate existing native position protection"
                    )
                if (
                    existing_plan is not None
                    and existing_plan.managed_exit.bracket is not None
                    and (
                        intent.stop_loss is not None
                        or intent.take_profit is not None
                        or intent.clear_take_profit
                    )
                ):
                    raise ValueError(
                        "native position protection cannot duplicate an existing managed bracket"
                    )
                existing_managed_stop = (
                    existing_plan is not None and existing_plan.managed_exit.bracket is not None
                )
                if (
                    position.stop_loss is None
                    and intent.stop_loss is None
                    and not existing_managed_stop
                    and (intent.managed_exit is None or intent.managed_exit.bracket is None)
                ):
                    raise ValueError("position protection must retain a bounded stop loss")
                if protection_basis is not None:
                    validate_directional_protection(
                        OrderType.BUY if is_buy else OrderType.SELL,
                        protection_basis,
                        intent.stop_loss,
                        intent.take_profit,
                        label="position protection",
                    )
                _validate_managed_relationships(
                    intent.managed_exit,
                    is_buy=is_buy,
                    basis=position.average_price,
                    label="position managed exit",
                    protection_basis=protection_basis,
                    validate_bracket=protection_basis is not None,
                )
            elif isinstance(intent, ClosePositionIntent):
                position = _position_by_id(context, intent.position_id)
                required_order_type = (
                    OrderType.SELL if position.side is PositionSide.BUY else OrderType.BUY
                )
                if required_order_type not in spec.order_types:
                    raise ValueError(
                        "position close deal type is not declared by the strategy spec"
                    )
                if not _has_executable_declared_filling(required_order_type, spec):
                    raise ValueError("position close has no market-legal declared filling policy")
            elif isinstance(intent, CloseByIntent):
                if spec.position_mode is not PositionMode.HEDGING:
                    raise ValueError("close-by requires HEDGING position mode")
                if OrderType.CLOSE_BY not in spec.order_types:
                    raise ValueError("CLOSE_BY is not declared by the strategy spec")
                position = _position_by_id(context, intent.position_id)
                opposite = _position_by_id(context, intent.opposite_position_id)
                if position.symbol is not opposite.symbol:
                    raise ValueError("close-by positions must share one symbol")
                if position.side is opposite.side:
                    raise ValueError("close-by positions must have opposite sides")
            elif isinstance(intent, ModifyOcoIntent):
                if Capability.PLATFORM_OCO not in spec.required_capabilities:
                    raise ValueError("OCO modification requires the PLATFORM_OCO capability")
                snapshot = next(
                    (
                        group
                        for group in context.oco_groups
                        if group.oco_group_id == intent.oco_group_id
                    ),
                    None,
                )
                if snapshot is None:
                    raise ValueError("intent target OCO group is not visible")
                if {leg.leg_id for leg in intent.group.legs} != {
                    leg.leg_id for leg in snapshot.legs
                }:
                    raise ValueError("replacement OCO group must preserve leg identities")
                _validate_group(intent.group, spec, context)
            elif isinstance(intent, CancelOcoIntent):
                if Capability.PLATFORM_OCO not in spec.required_capabilities:
                    raise ValueError("OCO cancellation requires the PLATFORM_OCO capability")
                if not any(
                    group.oco_group_id == intent.oco_group_id for group in context.oco_groups
                ):
                    raise ValueError("intent target OCO group is not visible")
            elif isinstance(intent, ModifyManagedExitIntent):
                snapshot = _plan_by_id(context, intent.managed_exit_plan_id)
                target = _plan_target(context, snapshot)
                _validate_managed_capabilities(intent.managed_exit, spec)
                if intent.managed_exit.bracket is not None and (
                    target.stop_loss is not None or target.take_profit is not None
                ):
                    raise ValueError(
                        "managed bracket cannot duplicate existing native target protection"
                    )
                if not _target_has_native_stop(target) and intent.managed_exit.bracket is None:
                    raise ValueError("managed plan replacement cannot remove the only stop loss")
                is_buy, basis = _target_side_and_basis(target)
                protection_basis = (
                    _latest_protection_basis(context, target.symbol, is_buy=is_buy)
                    if isinstance(target, Position)
                    else basis
                )
                _validate_managed_relationships(
                    intent.managed_exit,
                    is_buy=is_buy,
                    basis=basis,
                    label="managed plan replacement",
                    protection_basis=protection_basis,
                    validate_bracket=(
                        not isinstance(target, Position) or protection_basis is not None
                    ),
                )
            else:
                snapshot = _plan_by_id(context, intent.managed_exit_plan_id)
                target = _plan_target(context, snapshot)
                if not _target_has_native_stop(target):
                    raise ValueError("managed plan cannot be cleared without a native stop loss")
        return self


def validate_strategy_output(
    value: object,
    *,
    spec: StrategySpec,
    context: StrategyContext,
) -> StrategyOutput:
    """Validate untrusted output structurally and against its immutable inputs."""
    validated = _ContextualOutput.model_validate(
        {"output": value, "spec": spec, "context": context}
    )
    return validated.output
