from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

import trading_strategy_sdk as sdk

EVENT_TIME = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)


def _ohlc(value: Decimal) -> sdk.OHLC:
    return sdk.OHLC(open=value, high=value + Decimal("0.0002"), low=value, close=value)


def _subscription(symbol: sdk.Symbol = sdk.Symbol.EURUSD) -> sdk.BarSubscription:
    return sdk.BarSubscription(symbol=symbol, timeframe=sdk.Timeframe.M5)


def _bar(subscription: sdk.BarSubscription) -> sdk.ClosedBar:
    value = Decimal("2400" if subscription.symbol is sdk.Symbol.XAUUSD else "1.1000")
    return sdk.ClosedBar(
        subscription=subscription,
        open_time=EVENT_TIME - timedelta(minutes=5),
        close_time=EVENT_TIME,
        bid=_ohlc(value),
        ask=_ohlc(value + Decimal("0.0001")),
    )


def _spec(
    *,
    symbols: tuple[sdk.Symbol, ...] = (sdk.Symbol.EURUSD,),
    capabilities: frozenset[sdk.Capability] = frozenset(),
) -> sdk.StrategySpec:
    subscriptions = tuple(_subscription(symbol) for symbol in symbols)
    required = {sdk.Capability.RETURN_FILLING, *capabilities}
    if len(symbols) > 1:
        required.add(sdk.Capability.MULTI_SYMBOL_DATA)
    return sdk.StrategySpec(
        subscriptions=subscriptions,
        warmup=tuple(
            sdk.WarmupRequirement(subscription=subscription, bars=1)
            for subscription in subscriptions
        ),
        triggers=(sdk.TriggerSpec(name="active_close", subscriptions=(subscriptions[0],)),),
        synchronization=sdk.SynchronizationSpec(
            mode=sdk.SynchronizationMode.LATEST_CLOSED,
            required_subscriptions=subscriptions,
        ),
        entries=(sdk.RuleSpec(name="entry_rule", description="Enter."),),
        exits=(sdk.RuleSpec(name="exit_rule", description="Exit."),),
        position_mode=sdk.PositionMode.HEDGING,
        required_capabilities=frozenset(required),
        order_types=frozenset(
            {
                sdk.OrderType.BUY,
                sdk.OrderType.SELL,
                sdk.OrderType.BUY_LIMIT,
                sdk.OrderType.SELL_LIMIT,
                sdk.OrderType.BUY_STOP,
                sdk.OrderType.SELL_STOP,
                sdk.OrderType.BUY_STOP_LIMIT,
                sdk.OrderType.SELL_STOP_LIMIT,
                sdk.OrderType.CLOSE_BY,
            }
        ),
        filling_policies=frozenset({sdk.OrderFilling.RETURN}),
        disclosures=("Technical stop losses remain exposed to gaps.",),
        bounded_loss=sdk.BoundedLossSpec(
            stop_loss_required=True,
            gap_risk_disclosed=True,
            description="Every entry has a stop.",
        ),
    )


def _position(
    position_id: str = "position_1",
    *,
    stop_loss: Decimal | None = Decimal("1.0900"),
) -> sdk.Position:
    return sdk.Position(
        position_id=position_id,
        symbol=sdk.Symbol.EURUSD,
        side=sdk.PositionSide.BUY,
        average_price=Decimal("1.1000"),
        opened_at=EVENT_TIME - timedelta(minutes=5),
        stop_loss=stop_loss,
    )


def _context(
    spec: sdk.StrategySpec,
    *,
    positions: tuple[sdk.Position, ...] = (),
    pending_orders: tuple[object, ...] = (),
    oco_groups: tuple[object, ...] = (),
    managed_exit_plans: tuple[object, ...] = (),
    placement_results: tuple[object, ...] = (),
    lifecycle_results: tuple[object, ...] = (),
) -> sdk.StrategyContext:
    bars = tuple(_bar(subscription) for subscription in spec.subscriptions)
    return sdk.StrategyContext.model_validate(
        {
            "event": sdk.BarClosedEvent(event_time=EVENT_TIME, bar=bars[0]),
            "trigger": spec.triggers[0],
            "synchronization": spec.synchronization,
            "warmup": spec.warmup,
            "histories": tuple(
                sdk.BarSeries(subscription=bar.subscription, bars=(bar,)) for bar in bars
            ),
            "synchronized_bars": bars,
            "positions": sdk.PositionBook(mode=spec.position_mode, positions=positions),
            "position_mode": spec.position_mode,
            "pending_orders": pending_orders,
            "oco_groups": oco_groups,
            "managed_exit_plans": managed_exit_plans,
            "placement_results": placement_results,
            "lifecycle_results": lifecycle_results,
            "state": sdk.StrategyState.empty(),
        }
    )


def _validate_output(
    intent: object, *, spec: sdk.StrategySpec, context: sdk.StrategyContext
) -> object:
    return sdk.validate_strategy_output(
        {"signals": (), "intents": (intent,), "next_state": {}},
        spec=spec,
        context=context,
    )


def _pending_order(
    order_id: str = "order_1",
    *,
    symbol: sdk.Symbol = sdk.Symbol.EURUSD,
    order_type: sdk.OrderType = sdk.OrderType.BUY_LIMIT,
    placed_at: datetime = EVENT_TIME - timedelta(minutes=1),
    stop_loss: Decimal | None = Decimal("1.0900"),
    oco_group_id: str | None = None,
    managed_exit_plan_id: str | None = None,
) -> object:
    values: dict[str, Any] = {
        "order_id": order_id,
        "symbol": symbol,
        "order_type": order_type,
        "entry_price": Decimal("1.1000"),
        "stop_loss": stop_loss,
        "filling": sdk.OrderFilling.RETURN,
        "time": sdk.OrderTime.GTC,
        "placed_at": placed_at,
        "oco_group_id": oco_group_id,
        "managed_exit_plan_id": managed_exit_plan_id,
    }
    if order_type is sdk.OrderType.BUY_STOP_LIMIT:
        values["entry_price"] = Decimal("1.1050")
        values["stop_limit_price"] = Decimal("1.1040")
    elif order_type is sdk.OrderType.SELL_STOP_LIMIT:
        values["entry_price"] = Decimal("1.0950")
        values["stop_limit_price"] = Decimal("1.0960")
        values["stop_loss"] = stop_loss or Decimal("1.1050")
    return sdk.PendingOrder(**values)


def _managed_plan_snapshot(
    *,
    managed_exit_plan_id: str = "plan_1",
    position_id: str | None = "position_1",
    order_id: str | None = None,
    managed_exit: sdk.ManagedExitPlan | None = None,
    created_at: datetime = EVENT_TIME - timedelta(minutes=1),
) -> object:
    if managed_exit is None:
        managed_exit = sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(distance=Decimal("0.0050"))
        )
    return sdk.ManagedExitPlanSnapshot(
        managed_exit_plan_id=managed_exit_plan_id,
        position_id=position_id,
        order_id=order_id,
        managed_exit=managed_exit,
        created_at=created_at,
    )


def _oco_snapshot(
    *,
    oco_group_id: str = "breakout",
    first_order_id: str = "order_long",
    second_order_id: str = "order_short",
    created_at: datetime = EVENT_TIME - timedelta(minutes=1),
) -> object:
    return sdk.OcoGroupSnapshot(
        oco_group_id=oco_group_id,
        legs=(
            sdk.OcoLegSnapshot(leg_id="long", order_id=first_order_id),
            sdk.OcoLegSnapshot(leg_id="short", order_id=second_order_id),
        ),
        created_at=created_at,
    )


def _oco_definition(group_id: str = "breakout") -> sdk.OcoGroup:
    return sdk.OcoGroup(
        group_id=group_id,
        legs=(
            sdk.OcoLeg(
                leg_id="long",
                symbol=sdk.Symbol.EURUSD,
                order_type=sdk.OrderType.BUY_STOP,
                entry_price=Decimal("1.1050"),
                stop_loss=Decimal("1.0950"),
            ),
            sdk.OcoLeg(
                leg_id="short",
                symbol=sdk.Symbol.EURUSD,
                order_type=sdk.OrderType.SELL_STOP,
                entry_price=Decimal("1.0950"),
                stop_loss=Decimal("1.1050"),
            ),
        ),
    )


def test_pending_order_snapshot_round_trips_without_sizing_fields() -> None:
    pending = _pending_order()

    assert pending.order_id == "order_1"
    assert "volume" not in sdk.PendingOrder.model_fields
    assert sdk.PendingOrder.model_validate_json(pending.model_dump_json()) == pending


@pytest.mark.parametrize(
    "invalid_type", [sdk.OrderType.BUY, sdk.OrderType.SELL, sdk.OrderType.CLOSE_BY]
)
def test_pending_snapshot_rejects_every_non_pending_order_type(
    invalid_type: sdk.OrderType,
) -> None:
    with pytest.raises(ValidationError):
        _pending_order(order_type=invalid_type)


@pytest.mark.parametrize("filling", [sdk.OrderFilling.FOK, sdk.OrderFilling.IOC])
def test_pending_snapshot_rejects_immediate_filling_policy(filling: sdk.OrderFilling) -> None:
    with pytest.raises(ValidationError):
        sdk.PendingOrder(
            order_id="order_1",
            symbol=sdk.Symbol.EURUSD,
            order_type=sdk.OrderType.BUY_LIMIT,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0900"),
            filling=filling,
            placed_at=EVENT_TIME,
        )


def test_context_accepts_canonical_pending_oco_plan_and_result_snapshots() -> None:
    capabilities = frozenset(
        {
            sdk.Capability.PLATFORM_OCO,
            sdk.Capability.PLATFORM_TRAILING_STOP,
        }
    )
    spec = _spec(capabilities=capabilities)
    position = _position()
    pending = (
        _pending_order("order_long", oco_group_id="breakout"),
        _pending_order(
            "order_short",
            order_type=sdk.OrderType.SELL_LIMIT,
            stop_loss=Decimal("1.1100"),
            oco_group_id="breakout",
        ),
    )
    group = _oco_snapshot()
    plan = _managed_plan_snapshot()
    result = sdk.OcoPlacementResult(
        intent_id="oco_intent",
        oco_group_id="breakout",
        legs=(
            sdk.OcoLegPlacementResult(leg_id="long", order_id="order_long"),
            sdk.OcoLegPlacementResult(leg_id="short", order_id="order_short"),
        ),
        created_at=EVENT_TIME - timedelta(minutes=1),
    )
    lifecycle_result = sdk.OrderModifiedResult(
        intent_id="modify_intent",
        order_id="order_long",
        created_at=EVENT_TIME - timedelta(seconds=30),
    )

    context = _context(
        spec,
        positions=(position,),
        pending_orders=pending,
        oco_groups=(group,),
        managed_exit_plans=(plan,),
        placement_results=(result,),
        lifecycle_results=(lifecycle_result,),
    )

    assert tuple(order.order_id for order in context.pending_orders) == (
        "order_long",
        "order_short",
    )
    assert context.oco_groups == (group,)
    assert context.managed_exit_plans == (plan,)
    assert context.placement_results == (result,)
    assert context.lifecycle_results == (lifecycle_result,)
    assert sdk.StrategyContext.model_validate_json(context.model_dump_json()) == context


@pytest.mark.parametrize(
    "snapshot_field",
    [
        "pending_orders",
        "oco_groups",
        "managed_exit_plans",
        "placement_results",
        "lifecycle_results",
    ],
)
def test_context_rejects_future_lifecycle_snapshots(snapshot_field: str) -> None:
    spec = _spec()
    if snapshot_field == "pending_orders":
        value = (_pending_order(placed_at=EVENT_TIME + timedelta(seconds=1)),)
    elif snapshot_field == "oco_groups":
        value = (_oco_snapshot(created_at=EVENT_TIME + timedelta(seconds=1)),)
    elif snapshot_field == "managed_exit_plans":
        value = (_managed_plan_snapshot(created_at=EVENT_TIME + timedelta(seconds=1)),)
    elif snapshot_field == "placement_results":
        value = (
            sdk.OrderPlacementResult(
                intent_id="future_result",
                order_id="order_1",
                created_at=EVENT_TIME + timedelta(seconds=1),
            ),
        )
    else:
        value = (
            sdk.OrderCancelledResult(
                intent_id="future_cancel",
                order_id="order_1",
                created_at=EVENT_TIME + timedelta(seconds=1),
            ),
        )

    with pytest.raises(ValidationError):
        _context(spec, positions=(_position(),), **{snapshot_field: value})


def test_context_rejects_pending_order_for_undeclared_symbol() -> None:
    spec = _spec()

    with pytest.raises(ValidationError):
        _context(spec, pending_orders=(_pending_order(symbol=sdk.Symbol.XAUUSD),))


def test_context_rejects_duplicate_order_group_plan_and_result_ids() -> None:
    spec = _spec()
    pending = _pending_order()
    group = _oco_snapshot()
    plan = _managed_plan_snapshot()
    result = sdk.OrderPlacementResult(
        intent_id="place_1",
        order_id="order_1",
        created_at=EVENT_TIME - timedelta(minutes=1),
    )

    duplicate_cases = (
        {"pending_orders": (pending, pending)},
        {"oco_groups": (group, group)},
        {"managed_exit_plans": (plan, plan)},
        {"placement_results": (result, result)},
    )
    for updates in duplicate_cases:
        with pytest.raises(ValidationError):
            _context(spec, positions=(_position(),), **updates)


def test_oco_snapshot_must_reference_visible_member_orders_bidirectionally() -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_OCO}))
    group = _oco_snapshot()
    only_one_order = _pending_order("order_long", oco_group_id="breakout")

    with pytest.raises(ValidationError):
        _context(spec, pending_orders=(only_one_order,), oco_groups=(group,))

    mismatched = (
        _pending_order("order_long", oco_group_id="another_group"),
        _pending_order(
            "order_short",
            order_type=sdk.OrderType.SELL_LIMIT,
            stop_loss=Decimal("1.1100"),
            oco_group_id="another_group",
        ),
    )
    with pytest.raises(ValidationError):
        _context(spec, pending_orders=mismatched, oco_groups=(group,))


@pytest.mark.parametrize("target_kind", ["neither", "both", "missing_position", "missing_order"])
def test_managed_plan_snapshot_requires_exactly_one_visible_target(target_kind: str) -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_TRAILING_STOP}))
    position_id = None
    order_id = None
    positions: tuple[sdk.Position, ...] = ()
    pending_orders: tuple[object, ...] = ()
    if target_kind == "both":
        position_id = "position_1"
        order_id = "order_1"
        positions = (_position(),)
        pending_orders = (_pending_order(),)
    elif target_kind == "missing_position":
        position_id = "missing"
    elif target_kind == "missing_order":
        order_id = "missing"
    if target_kind in {"neither", "both"}:
        plan = sdk.ManagedExitPlanSnapshot.model_construct(
            managed_exit_plan_id="plan_1",
            position_id=position_id,
            order_id=order_id,
            managed_exit=sdk.ManagedExitPlan(
                trailing_stop=sdk.TrailingStop(distance=Decimal("0.0050"))
            ),
            created_at=EVENT_TIME - timedelta(minutes=1),
        )
    else:
        plan = _managed_plan_snapshot(position_id=position_id, order_id=order_id)

    with pytest.raises(ValidationError):
        _context(
            spec,
            positions=positions,
            pending_orders=pending_orders,
            managed_exit_plans=(plan,),
        )


def test_context_rejects_conflicting_or_orphaned_managed_plan_targets() -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_TRAILING_STOP}))
    position = _position()
    first = _managed_plan_snapshot(managed_exit_plan_id="plan_1")
    second = _managed_plan_snapshot(managed_exit_plan_id="plan_2")

    with pytest.raises(ValidationError):
        _context(spec, positions=(position,), managed_exit_plans=(first, second))

    pending = _pending_order(managed_exit_plan_id=None)
    orphan = _managed_plan_snapshot(
        managed_exit_plan_id="orphan", position_id=None, order_id="order_1"
    )
    with pytest.raises(ValidationError):
        _context(spec, pending_orders=(pending,), managed_exit_plans=(orphan,))


def test_context_rejects_native_and_managed_bracket_snapshot_conflicts() -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_BRACKETS}))
    bracket = sdk.ManagedExitPlan(
        bracket=sdk.BracketExit(stop_loss=Decimal("1.0900"), take_profit=Decimal("1.1200"))
    )
    with pytest.raises(ValidationError):
        _context(
            spec,
            positions=(_position(stop_loss=Decimal("1.0900")),),
            managed_exit_plans=(_managed_plan_snapshot(managed_exit=bracket),),
        )

    pending = _pending_order(managed_exit_plan_id="plan_1")
    order_plan = _managed_plan_snapshot(
        position_id=None,
        order_id="order_1",
        managed_exit=bracket,
    )
    with pytest.raises(ValidationError):
        _context(spec, pending_orders=(pending,), managed_exit_plans=(order_plan,))


@pytest.mark.parametrize("invalid_snapshot", ["pending_bracket", "position_trigger", "unbounded"])
def test_context_revalidates_managed_plan_snapshot_relationships(
    invalid_snapshot: str,
) -> None:
    capabilities = frozenset(
        {
            sdk.Capability.PLATFORM_BRACKETS,
            sdk.Capability.PLATFORM_BREAK_EVEN,
            sdk.Capability.PLATFORM_TRAILING_STOP,
        }
    )
    spec = _spec(capabilities=capabilities)
    if invalid_snapshot == "pending_bracket":
        pending = _pending_order(stop_loss=None, managed_exit_plan_id="plan_1")
        plan = _managed_plan_snapshot(
            position_id=None,
            order_id="order_1",
            managed_exit=sdk.ManagedExitPlan(
                bracket=sdk.BracketExit(stop_loss=Decimal("1.1100"), take_profit=Decimal("1.1200"))
            ),
        )
        kwargs = {"pending_orders": (pending,), "managed_exit_plans": (plan,)}
    elif invalid_snapshot == "position_trigger":
        position = _position()
        plan = _managed_plan_snapshot(
            managed_exit=sdk.ManagedExitPlan(
                break_even=sdk.BreakEven(trigger_price=Decimal("1.0900"))
            )
        )
        kwargs = {"positions": (position,), "managed_exit_plans": (plan,)}
    else:
        position = _position(stop_loss=None)
        plan = _managed_plan_snapshot()
        kwargs = {"positions": (position,), "managed_exit_plans": (plan,)}

    with pytest.raises(ValidationError):
        _context(spec, **kwargs)


def test_order_and_oco_results_expose_ids_consumed_by_existing_order_apis() -> None:
    order_result = sdk.OrderPlacementResult(
        intent_id="place_1",
        order_id="order_1",
        managed_exit_plan_id="plan_1",
        created_at=EVENT_TIME,
    )
    oco_result = sdk.OcoPlacementResult(
        intent_id="oco_1",
        oco_group_id="breakout",
        legs=(
            sdk.OcoLegPlacementResult(
                leg_id="long", order_id="order_long", managed_exit_plan_id="long_plan"
            ),
            sdk.OcoLegPlacementResult(leg_id="short", order_id="order_short"),
        ),
        created_at=EVENT_TIME,
    )

    modify = sdk.ModifyOrderIntent(
        intent_id="modify", order_id=order_result.order_id, entry_price=Decimal("1.1010")
    )
    cancel = sdk.CancelOrderIntent(intent_id="cancel", order_id=oco_result.legs[0].order_id)

    assert modify.order_id == "order_1"
    assert cancel.order_id == "order_long"
    assert oco_result.oco_group_id == "breakout"
    assert oco_result.legs[0].managed_exit_plan_id == "long_plan"


def test_placement_results_reject_duplicate_platform_issued_ids() -> None:
    created_at = EVENT_TIME - timedelta(minutes=1)
    first = sdk.OrderPlacementResult(
        intent_id="first",
        order_id="same_order",
        managed_exit_plan_id="same_plan",
        created_at=created_at,
    )
    duplicate_order = sdk.OrderPlacementResult(
        intent_id="second",
        order_id="same_order",
        created_at=created_at,
    )
    duplicate_plan = sdk.OrderPlacementResult(
        intent_id="third",
        order_id="other_order",
        managed_exit_plan_id="same_plan",
        created_at=created_at,
    )
    spec = _spec()
    for duplicate in (duplicate_order, duplicate_plan):
        with pytest.raises(ValidationError):
            _context(spec, placement_results=(first, duplicate))

    with pytest.raises(ValidationError):
        sdk.OcoPlacementResult(
            intent_id="oco",
            oco_group_id="group",
            legs=(
                sdk.OcoLegPlacementResult(
                    leg_id="long", order_id="long_order", managed_exit_plan_id="same_plan"
                ),
                sdk.OcoLegPlacementResult(
                    leg_id="short", order_id="short_order", managed_exit_plan_id="same_plan"
                ),
            ),
            created_at=created_at,
        )


def test_oco_leg_can_atomically_attach_every_managed_exit_feature() -> None:
    managed_exit = sdk.ManagedExitPlan(
        trailing_stop=sdk.TrailingStop(
            distance=Decimal("0.0050"), activation_price=Decimal("1.1100")
        ),
        break_even=sdk.BreakEven(trigger_price=Decimal("1.1100")),
        partials=(sdk.PartialExit(trigger_price=Decimal("1.1150"), fraction=Decimal("0.5")),),
    )

    leg = sdk.OcoLeg(
        leg_id="long",
        symbol=sdk.Symbol.EURUSD,
        order_type=sdk.OrderType.BUY_STOP,
        entry_price=Decimal("1.1050"),
        stop_loss=Decimal("1.0950"),
        managed_exit=managed_exit,
    )

    assert leg.managed_exit == managed_exit


def _lifecycle_intents() -> tuple[object, ...]:
    return (
        sdk.ModifyOcoIntent(
            intent_id="modify_oco",
            oco_group_id="breakout",
            group=_oco_definition(),
        ),
        sdk.CancelOcoIntent(intent_id="cancel_oco", oco_group_id="breakout"),
        sdk.ModifyManagedExitIntent(
            intent_id="modify_plan",
            managed_exit_plan_id="plan_1",
            managed_exit=sdk.ManagedExitPlan(
                trailing_stop=sdk.TrailingStop(distance=Decimal("0.0040"))
            ),
        ),
        sdk.ClearManagedExitIntent(intent_id="clear_plan", managed_exit_plan_id="plan_1"),
    )


def test_group_and_plan_lifecycle_intents_are_closed_platform_operations() -> None:
    for intent in _lifecycle_intents():
        assert intent.action is None
        assert sdk.validate_order_intent(intent.model_dump(mode="json")) == intent


@pytest.mark.parametrize(
    "intent_name",
    ["ModifyOcoIntent", "CancelOcoIntent", "ModifyManagedExitIntent", "ClearManagedExitIntent"],
)
def test_lifecycle_intent_rejects_unknown_snapshot_target(intent_name: str) -> None:
    spec = _spec(
        capabilities=frozenset({sdk.Capability.PLATFORM_OCO, sdk.Capability.PLATFORM_TRAILING_STOP})
    )
    if intent_name == "ModifyOcoIntent":
        intent = sdk.ModifyOcoIntent(
            intent_id="unknown", oco_group_id="missing", group=_oco_definition("missing")
        )
    elif intent_name == "CancelOcoIntent":
        intent = sdk.CancelOcoIntent(intent_id="unknown", oco_group_id="missing")
    elif intent_name == "ModifyManagedExitIntent":
        intent = sdk.ModifyManagedExitIntent(
            intent_id="unknown",
            managed_exit_plan_id="missing",
            managed_exit=sdk.ManagedExitPlan(
                trailing_stop=sdk.TrailingStop(distance=Decimal("0.0040"))
            ),
        )
    else:
        intent = sdk.ClearManagedExitIntent(intent_id="unknown", managed_exit_plan_id="missing")

    with pytest.raises(ValidationError):
        _validate_output(intent, spec=spec, context=_context(spec))


def test_visible_oco_group_can_be_modified_and_cancelled_atomically() -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_OCO}))
    pending = (
        _pending_order("order_long", oco_group_id="breakout"),
        _pending_order(
            "order_short",
            order_type=sdk.OrderType.SELL_LIMIT,
            stop_loss=Decimal("1.1100"),
            oco_group_id="breakout",
        ),
    )
    context = _context(spec, pending_orders=pending, oco_groups=(_oco_snapshot(),))
    intents = (
        sdk.ModifyOcoIntent(intent_id="modify", oco_group_id="breakout", group=_oco_definition()),
        sdk.CancelOcoIntent(intent_id="cancel", oco_group_id="breakout"),
    )

    for intent in intents:
        output = _validate_output(intent, spec=spec, context=context)
        assert output.intents == (intent,)


def test_oco_modification_uses_opaque_target_id_and_preserves_leg_identity() -> None:
    opaque_group_id = "123e4567-e89b-12d3-a456-426614174000"
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_OCO}))
    pending = (
        _pending_order("order_long", oco_group_id=opaque_group_id),
        _pending_order(
            "order_short",
            order_type=sdk.OrderType.SELL_LIMIT,
            stop_loss=Decimal("1.1100"),
            oco_group_id=opaque_group_id,
        ),
    )
    snapshot = _oco_snapshot(oco_group_id=opaque_group_id)
    context = _context(spec, pending_orders=pending, oco_groups=(snapshot,))
    valid = sdk.ModifyOcoIntent(
        intent_id="modify_opaque",
        oco_group_id=opaque_group_id,
        group=_oco_definition("breakout"),
    )
    assert _validate_output(valid, spec=spec, context=context).intents == (valid,)

    unrelated = sdk.ModifyOcoIntent(
        intent_id="replace_legs",
        oco_group_id=opaque_group_id,
        group=sdk.OcoGroup(
            group_id="breakout",
            legs=(
                sdk.OcoLeg(
                    leg_id="new_long",
                    symbol=sdk.Symbol.EURUSD,
                    order_type=sdk.OrderType.BUY_STOP,
                    entry_price=Decimal("1.1050"),
                    stop_loss=Decimal("1.0950"),
                ),
                sdk.OcoLeg(
                    leg_id="new_short",
                    symbol=sdk.Symbol.EURUSD,
                    order_type=sdk.OrderType.SELL_STOP,
                    entry_price=Decimal("1.0950"),
                    stop_loss=Decimal("1.1050"),
                ),
            ),
        ),
    )
    with pytest.raises(ValidationError):
        _validate_output(unrelated, spec=spec, context=context)


def test_managed_plan_cannot_be_cleared_when_it_holds_the_only_stop_loss() -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_BRACKETS}))
    position = _position(stop_loss=None)
    plan = _managed_plan_snapshot(
        managed_exit=sdk.ManagedExitPlan(
            bracket=sdk.BracketExit(stop_loss=Decimal("1.0900"), take_profit=Decimal("1.1200"))
        )
    )
    context = _context(spec, positions=(position,), managed_exit_plans=(plan,))
    clear = sdk.ClearManagedExitIntent(intent_id="clear", managed_exit_plan_id="plan_1")

    with pytest.raises(ValidationError):
        _validate_output(clear, spec=spec, context=context)


def test_managed_plan_can_be_cleared_when_native_stop_remains() -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_TRAILING_STOP}))
    position = _position(stop_loss=Decimal("1.0900"))
    plan = _managed_plan_snapshot()
    context = _context(spec, positions=(position,), managed_exit_plans=(plan,))
    clear = sdk.ClearManagedExitIntent(intent_id="clear", managed_exit_plan_id="plan_1")

    output = _validate_output(clear, spec=spec, context=context)

    assert output.intents == (clear,)


def test_managed_plan_replacement_cannot_remove_the_only_stop_loss() -> None:
    spec = _spec(
        capabilities=frozenset(
            {
                sdk.Capability.PLATFORM_BRACKETS,
                sdk.Capability.PLATFORM_TRAILING_STOP,
            }
        )
    )
    position = _position(stop_loss=None)
    plan = _managed_plan_snapshot(
        managed_exit=sdk.ManagedExitPlan(
            bracket=sdk.BracketExit(stop_loss=Decimal("1.0900"), take_profit=Decimal("1.1200"))
        )
    )
    context = _context(spec, positions=(position,), managed_exit_plans=(plan,))
    replace = sdk.ModifyManagedExitIntent(
        intent_id="replace",
        managed_exit_plan_id="plan_1",
        managed_exit=sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(distance=Decimal("0.0040"))
        ),
    )

    with pytest.raises(ValidationError):
        _validate_output(replace, spec=spec, context=context)


def test_managed_plan_replacement_revalidates_bracket_direction() -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_BRACKETS}))
    position = _position(stop_loss=None)
    plan = _managed_plan_snapshot(
        managed_exit=sdk.ManagedExitPlan(
            bracket=sdk.BracketExit(stop_loss=Decimal("1.0900"), take_profit=Decimal("1.1200"))
        )
    )
    context = _context(spec, positions=(position,), managed_exit_plans=(plan,))
    replace = sdk.ModifyManagedExitIntent(
        intent_id="replace_bad_bracket",
        managed_exit_plan_id="plan_1",
        managed_exit=sdk.ManagedExitPlan(
            bracket=sdk.BracketExit(stop_loss=Decimal("1.1100"), take_profit=Decimal("1.1200"))
        ),
    )

    with pytest.raises(ValidationError):
        _validate_output(replace, spec=spec, context=context)


def test_output_rejects_native_managed_conflicts_and_duplicate_plans() -> None:
    capabilities = frozenset(
        {sdk.Capability.PLATFORM_BRACKETS, sdk.Capability.PLATFORM_TRAILING_STOP}
    )
    spec = _spec(capabilities=capabilities)
    native_position = _position(stop_loss=Decimal("1.0900"))
    native_context = _context(spec, positions=(native_position,))
    add_bracket = sdk.ProtectPositionIntent(
        intent_id="add_bracket",
        position_id="position_1",
        managed_exit=sdk.ManagedExitPlan(
            bracket=sdk.BracketExit(stop_loss=Decimal("1.0900"), take_profit=Decimal("1.1200"))
        ),
    )
    with pytest.raises(ValidationError):
        _validate_output(add_bracket, spec=spec, context=native_context)

    unprotected = _position(stop_loss=None)
    bracket_plan = _managed_plan_snapshot(
        managed_exit=sdk.ManagedExitPlan(
            bracket=sdk.BracketExit(stop_loss=Decimal("1.0900"), take_profit=Decimal("1.1200"))
        )
    )
    bracket_context = _context(spec, positions=(unprotected,), managed_exit_plans=(bracket_plan,))
    add_native = sdk.ProtectPositionIntent(
        intent_id="add_native", position_id="position_1", stop_loss=Decimal("1.0900")
    )
    with pytest.raises(ValidationError):
        _validate_output(add_native, spec=spec, context=bracket_context)

    trailing_plan = _managed_plan_snapshot()
    trailing_context = _context(
        spec, positions=(native_position,), managed_exit_plans=(trailing_plan,)
    )
    add_second_plan = sdk.ProtectPositionIntent(
        intent_id="second_plan",
        position_id="position_1",
        managed_exit=sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(distance=Decimal("0.0040"))
        ),
    )
    with pytest.raises(ValidationError):
        _validate_output(add_second_plan, spec=spec, context=trailing_context)

    replace_with_bracket = sdk.ModifyManagedExitIntent(
        intent_id="replace_with_bracket",
        managed_exit_plan_id="plan_1",
        managed_exit=add_bracket.managed_exit,
    )
    with pytest.raises(ValidationError):
        _validate_output(replace_with_bracket, spec=spec, context=trailing_context)


def test_modify_order_revalidates_its_attached_managed_plan() -> None:
    capabilities = frozenset(
        {sdk.Capability.PLATFORM_BRACKETS, sdk.Capability.PLATFORM_TRAILING_STOP}
    )
    spec = _spec(capabilities=capabilities)
    pending = _pending_order(managed_exit_plan_id="plan_1")
    trailing = _managed_plan_snapshot(
        position_id=None,
        order_id="order_1",
        managed_exit=sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(
                distance=Decimal("0.0050"), activation_price=Decimal("1.1100")
            )
        ),
    )
    context = _context(spec, pending_orders=(pending,), managed_exit_plans=(trailing,))
    move_past_trigger = sdk.ModifyOrderIntent(
        intent_id="move_past_trigger",
        order_id="order_1",
        entry_price=Decimal("1.1200"),
    )
    with pytest.raises(ValidationError):
        _validate_output(move_past_trigger, spec=spec, context=context)

    managed_only = _pending_order(stop_loss=None, managed_exit_plan_id="plan_1")
    bracket = _managed_plan_snapshot(
        position_id=None,
        order_id="order_1",
        managed_exit=sdk.ManagedExitPlan(
            bracket=sdk.BracketExit(stop_loss=Decimal("1.0900"), take_profit=Decimal("1.1200"))
        ),
    )
    bracket_context = _context(spec, pending_orders=(managed_only,), managed_exit_plans=(bracket,))
    add_native = sdk.ModifyOrderIntent(
        intent_id="add_native", order_id="order_1", stop_loss=Decimal("1.0900")
    )
    with pytest.raises(ValidationError):
        _validate_output(add_native, spec=spec, context=bracket_context)


@pytest.mark.parametrize(
    ("change", "value"),
    [
        ("stop_loss", Decimal("1.1045")),
        ("entry_price", Decimal("1.1030")),
        ("stop_limit_price", Decimal("1.1060")),
    ],
)
def test_modify_order_revalidates_stop_limit_against_full_visible_snapshot(
    change: str, value: Decimal
) -> None:
    spec = _spec()
    pending = _pending_order(
        order_type=sdk.OrderType.BUY_STOP_LIMIT,
        stop_loss=Decimal("1.1030"),
    )
    context = _context(spec, pending_orders=(pending,))
    intent = sdk.ModifyOrderIntent(
        intent_id="modify_stop_limit",
        order_id="order_1",
        **{change: value},
    )

    with pytest.raises(ValidationError):
        _validate_output(intent, spec=spec, context=context)


@pytest.mark.parametrize("intent_name", ["ModifyOrderIntent", "CancelOrderIntent"])
def test_existing_order_lifecycle_intents_require_visible_pending_order(
    intent_name: str,
) -> None:
    spec = _spec()
    if intent_name == "ModifyOrderIntent":
        intent = sdk.ModifyOrderIntent(
            intent_id="missing", order_id="missing", entry_price=Decimal("1.1010")
        )
    else:
        intent = sdk.CancelOrderIntent(intent_id="missing", order_id="missing")

    with pytest.raises(ValidationError):
        _validate_output(intent, spec=spec, context=_context(spec))
