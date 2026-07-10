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


def _bar(
    subscription: sdk.BarSubscription,
    value: str = "1.1000",
    close_time: datetime = EVENT_TIME,
) -> sdk.ClosedBar:
    bid = Decimal(value)
    return sdk.ClosedBar(
        subscription=subscription,
        open_time=close_time - timedelta(minutes=subscription.timeframe.minutes),
        close_time=close_time,
        bid=_ohlc(bid),
        ask=_ohlc(bid + Decimal("0.0001")),
    )


def _spec(
    *,
    symbols: tuple[sdk.Symbol, ...] = (sdk.Symbol.EURUSD,),
    position_mode: sdk.PositionMode = sdk.PositionMode.HEDGING,
    order_types: frozenset[sdk.OrderType] | None = None,
    filling_policies: frozenset[sdk.OrderFilling] = frozenset({sdk.OrderFilling.RETURN}),
    capabilities: frozenset[sdk.Capability] = frozenset(),
) -> sdk.StrategySpec:
    subscriptions = tuple(
        sdk.BarSubscription(symbol=symbol, timeframe=sdk.Timeframe.M5) for symbol in symbols
    )
    required_capabilities = {sdk.Capability.RETURN_FILLING, *capabilities}
    if len(symbols) > 1:
        required_capabilities.add(sdk.Capability.MULTI_SYMBOL_DATA)
    if order_types is None:
        declared_order_types = {
            sdk.OrderType.BUY,
            sdk.OrderType.SELL,
            sdk.OrderType.BUY_LIMIT,
            sdk.OrderType.SELL_LIMIT,
            sdk.OrderType.BUY_STOP,
            sdk.OrderType.SELL_STOP,
            sdk.OrderType.BUY_STOP_LIMIT,
            sdk.OrderType.SELL_STOP_LIMIT,
        }
        if position_mode is sdk.PositionMode.HEDGING:
            declared_order_types.add(sdk.OrderType.CLOSE_BY)
        order_types = frozenset(declared_order_types)
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
        entries=(sdk.RuleSpec(name="entry_rule", description="Enter on a valid signal."),),
        exits=(sdk.RuleSpec(name="exit_rule", description="Exit or protect an open trade."),),
        position_mode=position_mode,
        required_capabilities=frozenset(required_capabilities),
        order_types=order_types,
        filling_policies=filling_policies,
        disclosures=("Technical stop losses remain exposed to market gaps.",),
        bounded_loss=sdk.BoundedLossSpec(
            stop_loss_required=True,
            gap_risk_disclosed=True,
            description="Every entry has a technical loss bound.",
        ),
    )


def _position(
    position_id: str,
    *,
    symbol: sdk.Symbol = sdk.Symbol.EURUSD,
    side: sdk.PositionSide = sdk.PositionSide.BUY,
    stop_loss: Decimal | None = Decimal("1.0900"),
) -> sdk.Position:
    average_price = Decimal("1.1000") if symbol is not sdk.Symbol.XAUUSD else Decimal("2400")
    return sdk.Position(
        position_id=position_id,
        symbol=symbol,
        side=side,
        volume=Decimal("0.10"),
        average_price=average_price,
        opened_at=EVENT_TIME - timedelta(minutes=5),
        stop_loss=stop_loss,
    )


def _context(
    spec: sdk.StrategySpec,
    *,
    present_symbols: tuple[sdk.Symbol, ...] | None = None,
    warmup_bars: int = 1,
    positions: tuple[sdk.Position, ...] = (),
    position_mode: sdk.PositionMode | None = None,
    bar_values: dict[sdk.Symbol, str] | None = None,
    **updates: object,
) -> sdk.StrategyContext:
    subscriptions = spec.subscriptions
    if present_symbols is None:
        present_symbols = tuple(subscription.symbol for subscription in subscriptions)
    bars = {
        subscription.key: _bar(
            subscription,
            (bar_values or {}).get(
                subscription.symbol,
                "2400" if subscription.symbol is sdk.Symbol.XAUUSD else "1.1000",
            ),
        )
        for subscription in subscriptions
        if subscription.symbol in present_symbols
    }
    event_subscription = subscriptions[0]
    event_bar = bars[event_subscription.key]
    values: dict[str, object] = {
        "event": sdk.BarClosedEvent(event_time=EVENT_TIME, bar=event_bar),
        "trigger": spec.triggers[0],
        "synchronization": spec.synchronization,
        "warmup": tuple(
            sdk.WarmupRequirement(subscription=subscription, bars=warmup_bars)
            for subscription in subscriptions
        ),
        "histories": tuple(
            sdk.BarSeries(subscription=subscription, bars=(bars[subscription.key],))
            for subscription in subscriptions
            if subscription.key in bars
        ),
        "synchronized_bars": tuple(bars.values()),
        "positions": sdk.PositionBook(
            mode=position_mode or spec.position_mode,
            positions=positions,
        ),
        "position_mode": position_mode or spec.position_mode,
        "state": sdk.StrategyState.empty(),
    }
    values.update(updates)
    return sdk.StrategyContext.model_validate(values)


def _validate_output(
    *,
    spec: sdk.StrategySpec,
    context: sdk.StrategyContext,
    signals: tuple[object, ...] = (),
    intents: tuple[object, ...] = (),
) -> sdk.StrategyOutput:
    return sdk.validate_strategy_output(
        {
            "signals": signals,
            "intents": intents,
            "next_state": {},
        },
        spec=spec,
        context=context,
    )


def _signal(
    symbol: sdk.Symbol = sdk.Symbol.EURUSD, rule_name: str = "entry_rule"
) -> sdk.SignalIntent:
    return sdk.SignalIntent(
        signal_id="signal_1",
        rule_name=rule_name,
        symbol=symbol,
        side=sdk.PositionSide.BUY,
        reference_price=Decimal("1.1000"),
        stop_loss=Decimal("1.0900"),
    )


def _place_order(
    *,
    symbol: sdk.Symbol = sdk.Symbol.EURUSD,
    order_type: sdk.OrderType = sdk.OrderType.BUY_LIMIT,
    filling: sdk.OrderFilling = sdk.OrderFilling.RETURN,
    managed_exit: sdk.ManagedExitPlan | None = None,
) -> sdk.PlaceOrderIntent:
    is_market = order_type.is_market
    is_buy = order_type.is_buy
    values: dict[str, Any] = {
        "intent_id": "place_1",
        "symbol": symbol,
        "order_type": order_type,
        "entry_price": None if is_market else Decimal("1.1000"),
        "filling": filling,
        "managed_exit": managed_exit,
    }
    if managed_exit is None or managed_exit.bracket is None:
        values["stop_loss"] = Decimal("1.0900" if is_buy else "1.1100")
    return sdk.PlaceOrderIntent(**values)


def _oco(
    *,
    first_symbol: sdk.Symbol = sdk.Symbol.EURUSD,
    second_symbol: sdk.Symbol = sdk.Symbol.EURUSD,
    filling: sdk.OrderFilling = sdk.OrderFilling.RETURN,
) -> sdk.PlaceOcoIntent:
    passive = filling is sdk.OrderFilling.BOC
    return sdk.PlaceOcoIntent(
        intent_id="oco_1",
        group=sdk.OcoGroup(
            group_id="breakout",
            legs=(
                sdk.OcoLeg(
                    leg_id="long",
                    symbol=first_symbol,
                    order_type=(sdk.OrderType.BUY_LIMIT if passive else sdk.OrderType.BUY_STOP),
                    entry_price=Decimal("1.1000" if passive else "1.1050"),
                    stop_loss=Decimal("1.0900"),
                    filling=filling,
                ),
                sdk.OcoLeg(
                    leg_id="short",
                    symbol=second_symbol,
                    order_type=(sdk.OrderType.SELL_LIMIT if passive else sdk.OrderType.SELL_STOP),
                    entry_price=Decimal("1.1000" if passive else "1.0950"),
                    stop_loss=Decimal("1.1100"),
                    filling=filling,
                ),
            ),
        ),
    )


@pytest.mark.parametrize("output_kind", ["signal", "place_order", "place_oco"])
def test_output_symbols_must_be_declared_by_the_spec(output_kind: str) -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_OCO}))
    context = _context(spec)
    if output_kind == "signal":
        kwargs = {"signals": (_signal(sdk.Symbol.XAUUSD),)}
    elif output_kind == "place_order":
        kwargs = {"intents": (_place_order(symbol=sdk.Symbol.XAUUSD),)}
    else:
        kwargs = {"intents": (_oco(second_symbol=sdk.Symbol.XAUUSD),)}

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=context, **kwargs)


def test_signal_rule_name_must_be_a_declared_entry_rule() -> None:
    spec = _spec()

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), signals=(_signal(rule_name="unknown"),))


def test_order_intent_validator_can_enforce_spec_and_context_semantics() -> None:
    spec = _spec()
    context = _context(spec)
    valid = _place_order()

    assert sdk.validate_order_intent(valid, spec=spec, context=context) == valid
    with pytest.raises(ValidationError):
        sdk.validate_order_intent(
            _place_order(symbol=sdk.Symbol.XAUUSD),
            spec=spec,
            context=context,
        )


def test_place_order_type_must_be_declared_by_the_spec() -> None:
    spec = _spec(order_types=frozenset({sdk.OrderType.BUY}))

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), intents=(_place_order(),))


def test_every_oco_leg_order_type_must_be_declared_by_the_spec() -> None:
    spec = _spec(
        order_types=frozenset({sdk.OrderType.BUY_STOP}),
        capabilities=frozenset({sdk.Capability.PLATFORM_OCO}),
    )

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), intents=(_oco(),))


@pytest.mark.parametrize("output_kind", ["place_order", "place_oco"])
def test_order_filling_must_be_declared_by_the_spec(output_kind: str) -> None:
    capabilities = (
        frozenset({sdk.Capability.PLATFORM_OCO}) if output_kind == "place_oco" else frozenset()
    )
    spec = _spec(capabilities=capabilities)
    if output_kind == "place_order":
        intent = _place_order(order_type=sdk.OrderType.BUY, filling=sdk.OrderFilling.IOC)
    else:
        intent = _oco(filling=sdk.OrderFilling.BOC)

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), intents=(intent,))


def test_platform_oco_requires_its_declared_capability() -> None:
    without = _spec()
    with pytest.raises(ValidationError):
        _validate_output(spec=without, context=_context(without), intents=(_oco(),))

    enabled = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_OCO}))
    output = _validate_output(spec=enabled, context=_context(enabled), intents=(_oco(),))
    assert output.intents[0].kind == "place_oco"


def _managed_plan(feature: str, *, valid_direction: bool = True) -> sdk.ManagedExitPlan:
    if feature == "bracket":
        return sdk.ManagedExitPlan(
            bracket=sdk.BracketExit(stop_loss=Decimal("1.0900"), take_profit=Decimal("1.1200"))
        )
    if feature == "trailing_stop":
        return sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(
                distance=Decimal("0.0050"),
                activation_price=Decimal("1.1100" if valid_direction else "1.0900"),
            )
        )
    if feature == "break_even":
        return sdk.ManagedExitPlan(
            break_even=sdk.BreakEven(
                trigger_price=Decimal("1.1100" if valid_direction else "1.0900")
            )
        )
    return sdk.ManagedExitPlan(
        partials=(
            sdk.PartialExit(
                trigger_price=Decimal("1.1100" if valid_direction else "1.0900"),
                fraction=Decimal("0.5"),
            ),
        )
    )


@pytest.mark.parametrize(
    ("feature", "capability"),
    [
        ("bracket", sdk.Capability.PLATFORM_BRACKETS),
        ("trailing_stop", sdk.Capability.PLATFORM_TRAILING_STOP),
        ("break_even", sdk.Capability.PLATFORM_BREAK_EVEN),
        ("partials", sdk.Capability.PLATFORM_PARTIAL_EXITS),
    ],
)
def test_each_managed_feature_requires_its_own_capability(
    feature: str, capability: sdk.Capability
) -> None:
    intent = _place_order(managed_exit=_managed_plan(feature))
    without = _spec()
    with pytest.raises(ValidationError):
        _validate_output(spec=without, context=_context(without), intents=(intent,))

    enabled = _spec(capabilities=frozenset({capability}))
    output = _validate_output(spec=enabled, context=_context(enabled), intents=(intent,))
    assert isinstance(output.intents[0], sdk.PlaceOrderIntent)
    assert output.intents[0].managed_exit is not None


@pytest.mark.parametrize("output_kind", ["signal", "place_order", "place_oco"])
def test_data_incomplete_blocks_every_form_of_new_entry(output_kind: str) -> None:
    spec = _spec(
        symbols=(sdk.Symbol.EURUSD, sdk.Symbol.XAUUSD),
        capabilities=frozenset({sdk.Capability.PLATFORM_OCO}),
    )
    context = _context(spec, present_symbols=(sdk.Symbol.EURUSD,))
    if output_kind == "signal":
        kwargs = {"signals": (_signal(),)}
    elif output_kind == "place_order":
        kwargs = {"intents": (_place_order(),)}
    else:
        kwargs = {"intents": (_oco(),)}

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=context, **kwargs)


def test_warmup_incomplete_blocks_entry_signal() -> None:
    spec = _spec()
    context = _context(spec, warmup_bars=2)

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=context, signals=(_signal(),))


def test_entry_blockers_do_not_disable_protective_exit_intents() -> None:
    spec = _spec(symbols=(sdk.Symbol.EURUSD, sdk.Symbol.XAUUSD))
    position = _position("position_1")
    context = _context(
        spec,
        present_symbols=(sdk.Symbol.EURUSD,),
        positions=(position,),
    )
    close = sdk.ClosePositionIntent(intent_id="close", position_id=position.position_id)

    output = _validate_output(spec=spec, context=context, intents=(close,))

    assert output.intents == (close,)


def test_context_position_mode_must_match_the_immutable_spec() -> None:
    spec = _spec(position_mode=sdk.PositionMode.HEDGING)
    context = _context(spec, position_mode=sdk.PositionMode.NETTING)

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=context)


@pytest.mark.parametrize("intent_name", ["ClosePositionIntent", "ProtectPositionIntent"])
def test_position_target_intents_require_a_visible_position(intent_name: str) -> None:
    spec = _spec()
    values: dict[str, object] = {"intent_id": "missing", "position_id": "missing"}
    if intent_name == "ProtectPositionIntent":
        values["stop_loss"] = Decimal("1.0900")
    intent = getattr(sdk, intent_name)(**values)

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), intents=(intent,))


def test_close_by_accepts_visible_opposite_hedged_positions_on_one_symbol() -> None:
    spec = _spec(position_mode=sdk.PositionMode.HEDGING)
    buy = _position("buy", side=sdk.PositionSide.BUY)
    sell = _position("sell", side=sdk.PositionSide.SELL, stop_loss=Decimal("1.1100"))
    context = _context(spec, positions=(buy, sell))
    intent = sdk.CloseByIntent(
        intent_id="close_by", position_id=buy.position_id, opposite_position_id=sell.position_id
    )

    output = _validate_output(spec=spec, context=context, intents=(intent,))

    assert output.intents == (intent,)


@pytest.mark.parametrize("invalid_relationship", ["same_side", "different_symbol", "missing"])
def test_close_by_rejects_invalid_position_relationships(invalid_relationship: str) -> None:
    symbols = (
        (sdk.Symbol.EURUSD, sdk.Symbol.XAUUSD)
        if invalid_relationship == "different_symbol"
        else (sdk.Symbol.EURUSD,)
    )
    spec = _spec(symbols=symbols, position_mode=sdk.PositionMode.HEDGING)
    buy = _position("buy")
    if invalid_relationship == "same_side":
        other = _position("other", side=sdk.PositionSide.BUY)
        opposite_id = other.position_id
        positions = (buy, other)
    elif invalid_relationship == "different_symbol":
        other = _position(
            "other",
            symbol=sdk.Symbol.XAUUSD,
            side=sdk.PositionSide.SELL,
            stop_loss=Decimal("2410"),
        )
        opposite_id = other.position_id
        positions = (buy, other)
    else:
        opposite_id = "missing"
        positions = (buy,)
    context = _context(spec, positions=positions)
    intent = sdk.CloseByIntent(
        intent_id="invalid_close_by",
        position_id=buy.position_id,
        opposite_position_id=opposite_id,
    )

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=context, intents=(intent,))


def test_close_by_is_rejected_in_netting_mode() -> None:
    spec = _spec(position_mode=sdk.PositionMode.NETTING)
    position = _position("one")
    context = _context(spec, positions=(position,))
    intent = sdk.CloseByIntent(
        intent_id="netting_close_by",
        position_id=position.position_id,
        opposite_position_id="other",
    )

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=context, intents=(intent,))


@pytest.mark.parametrize(
    ("feature", "capability"),
    [
        ("trailing_stop", sdk.Capability.PLATFORM_TRAILING_STOP),
        ("break_even", sdk.Capability.PLATFORM_BREAK_EVEN),
        ("partials", sdk.Capability.PLATFORM_PARTIAL_EXITS),
    ],
)
@pytest.mark.parametrize("order_type", [sdk.OrderType.BUY_LIMIT, sdk.OrderType.SELL_LIMIT])
def test_managed_profit_triggers_must_be_favorable_from_entry_basis(
    feature: str, capability: sdk.Capability, order_type: sdk.OrderType
) -> None:
    invalid_plan = _managed_plan(feature, valid_direction=order_type is sdk.OrderType.SELL_LIMIT)
    if order_type is sdk.OrderType.SELL_LIMIT:
        invalid_plan = _managed_plan(feature, valid_direction=True)
    intent = _place_order(order_type=order_type, managed_exit=invalid_plan)
    spec = _spec(capabilities=frozenset({capability}))

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), intents=(intent,))


@pytest.mark.parametrize(
    ("feature", "capability"),
    [
        ("trailing_stop", sdk.Capability.PLATFORM_TRAILING_STOP),
        ("break_even", sdk.Capability.PLATFORM_BREAK_EVEN),
        ("partials", sdk.Capability.PLATFORM_PARTIAL_EXITS),
    ],
)
def test_managed_profit_triggers_accept_favorable_direction(
    feature: str, capability: sdk.Capability
) -> None:
    intent = _place_order(managed_exit=_managed_plan(feature, valid_direction=True))
    spec = _spec(capabilities=frozenset({capability}))

    output = _validate_output(spec=spec, context=_context(spec), intents=(intent,))

    assert output.intents == (intent,)


@pytest.mark.parametrize(
    ("managed_exit", "capability"),
    [
        (
            sdk.ManagedExitPlan(
                break_even=sdk.BreakEven(trigger_price=Decimal("1.1100"), offset=Decimal("0.0200"))
            ),
            sdk.Capability.PLATFORM_BREAK_EVEN,
        ),
        (
            sdk.ManagedExitPlan(
                break_even=sdk.BreakEven(trigger_price=Decimal("1.1100"), offset=Decimal("-2.0000"))
            ),
            sdk.Capability.PLATFORM_BREAK_EVEN,
        ),
        (
            sdk.ManagedExitPlan(
                trailing_stop=sdk.TrailingStop(
                    distance=Decimal("2.0000"), activation_price=Decimal("1.1100")
                )
            ),
            sdk.Capability.PLATFORM_TRAILING_STOP,
        ),
    ],
)
def test_managed_features_cannot_derive_invalid_protection_prices(
    managed_exit: sdk.ManagedExitPlan,
    capability: sdk.Capability,
) -> None:
    intent = _place_order(managed_exit=managed_exit)
    spec = _spec(capabilities=frozenset({capability}))

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), intents=(intent,))


@pytest.mark.parametrize("intent_kind", ["protect", "modify_managed"])
@pytest.mark.parametrize(
    ("average_price", "current_bid", "distance", "valid"),
    [
        (Decimal("2.0000"), "1.1000", Decimal("1.5000"), False),
        (Decimal("1.1000"), "2.0000", Decimal("1.5000"), True),
    ],
)
def test_immediate_position_trailing_uses_current_protection_basis_when_visible(
    intent_kind: str,
    average_price: Decimal,
    current_bid: str,
    distance: Decimal,
    valid: bool,
) -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_TRAILING_STOP}))
    position = sdk.Position(
        position_id="position_1",
        symbol=sdk.Symbol.EURUSD,
        side=sdk.PositionSide.BUY,
        volume=Decimal("0.1"),
        average_price=average_price,
        opened_at=EVENT_TIME - timedelta(minutes=5),
        stop_loss=Decimal("1.0000"),
    )
    plan_snapshot = sdk.ManagedExitPlanSnapshot(
        managed_exit_plan_id="managed-plan/opaque",
        position_id=position.position_id,
        managed_exit=sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(
                distance=Decimal("0.1000"),
                activation_price=average_price + Decimal("0.2000"),
            )
        ),
        created_at=EVENT_TIME - timedelta(minutes=1),
    )
    context = _context(
        spec,
        positions=(position,),
        bar_values={sdk.Symbol.EURUSD: current_bid},
        managed_exit_plans=(plan_snapshot,) if intent_kind == "modify_managed" else (),
    )
    replacement = sdk.ManagedExitPlan(trailing_stop=sdk.TrailingStop(distance=distance))
    intent = (
        sdk.ModifyManagedExitIntent(
            intent_id="modify_trailing",
            managed_exit_plan_id=plan_snapshot.managed_exit_plan_id,
            managed_exit=replacement,
        )
        if intent_kind == "modify_managed"
        else sdk.ProtectPositionIntent(
            intent_id="protect_trailing",
            position_id=position.position_id,
            managed_exit=replacement,
        )
    )

    if valid:
        output = _validate_output(spec=spec, context=context, intents=(intent,))
        assert output.intents == (intent,)
    else:
        with pytest.raises(ValidationError):
            _validate_output(spec=spec, context=context, intents=(intent,))


@pytest.mark.parametrize("protection_kind", ["native", "managed_bracket"])
@pytest.mark.parametrize("order_type", [sdk.OrderType.BUY, sdk.OrderType.SELL])
def test_market_entry_stop_uses_executable_protection_side_of_spread(
    protection_kind: str, order_type: sdk.OrderType
) -> None:
    capabilities = (
        frozenset({sdk.Capability.PLATFORM_BRACKETS})
        if protection_kind == "managed_bracket"
        else frozenset()
    )
    spec = _spec(capabilities=capabilities)
    inside_spread = Decimal("1.10005")
    managed_exit = (
        sdk.ManagedExitPlan(
            bracket=sdk.BracketExit(
                stop_loss=inside_spread,
                take_profit=Decimal("1.1200" if order_type.is_buy else "1.0800"),
            )
        )
        if protection_kind == "managed_bracket"
        else None
    )
    intent = sdk.PlaceOrderIntent(
        intent_id="market_spread_stop",
        symbol=sdk.Symbol.EURUSD,
        order_type=order_type,
        stop_loss=inside_spread if managed_exit is None else None,
        managed_exit=managed_exit,
    )

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), intents=(intent,))


def test_immediate_market_trailing_uses_executable_protection_side() -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_TRAILING_STOP}))
    intent = sdk.PlaceOrderIntent(
        intent_id="market_trailing_spread",
        symbol=sdk.Symbol.EURUSD,
        order_type=sdk.OrderType.BUY,
        stop_loss=Decimal("1.0900"),
        managed_exit=sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(distance=Decimal("1.10005"))
        ),
    )

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), intents=(intent,))


@pytest.mark.parametrize(
    ("older_synchronized_bid", "newer_history_bid", "valid"),
    [("1.1000", "2.0000", True), ("2.0000", "1.1000", False)],
)
def test_protection_basis_uses_latest_visible_bar_across_snapshot_and_histories(
    older_synchronized_bid: str, newer_history_bid: str, valid: bool
) -> None:
    m5 = sdk.BarSubscription(symbol=sdk.Symbol.EURUSD, timeframe=sdk.Timeframe.M5)
    m15 = sdk.BarSubscription(symbol=sdk.Symbol.EURUSD, timeframe=sdk.Timeframe.M15)
    base = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_TRAILING_STOP}))
    spec = base.model_copy(
        update={
            "subscriptions": (m5, m15),
            "warmup": (
                sdk.WarmupRequirement(subscription=m5, bars=1),
                sdk.WarmupRequirement(subscription=m15, bars=1),
            ),
            "triggers": (sdk.TriggerSpec(name="active_close", subscriptions=(m5,)),),
            "synchronization": sdk.SynchronizationSpec(
                mode=sdk.SynchronizationMode.LATEST_CLOSED,
                required_subscriptions=(m5, m15),
            ),
            "required_capabilities": frozenset(
                {
                    *base.required_capabilities,
                    sdk.Capability.MULTI_TIMEFRAME_DATA,
                }
            ),
        }
    )
    event_bar = _bar(m5, newer_history_bid)
    older_bar = _bar(
        m15,
        older_synchronized_bid,
        close_time=EVENT_TIME - timedelta(minutes=5),
    )
    position = sdk.Position(
        position_id="position_1",
        symbol=sdk.Symbol.EURUSD,
        side=sdk.PositionSide.BUY,
        volume=Decimal("0.1"),
        average_price=Decimal("1.1000"),
        opened_at=EVENT_TIME - timedelta(minutes=30),
        stop_loss=Decimal("1.0000"),
    )
    context = sdk.StrategyContext(
        event=sdk.BarClosedEvent(event_time=EVENT_TIME, bar=event_bar),
        trigger=spec.triggers[0],
        synchronization=spec.synchronization,
        warmup=spec.warmup,
        histories=(
            sdk.BarSeries(subscription=m5, bars=(event_bar,)),
            sdk.BarSeries(subscription=m15, bars=(older_bar,)),
        ),
        synchronized_bars=(older_bar,),
        position_mode=spec.position_mode,
        positions=sdk.PositionBook(mode=spec.position_mode, positions=(position,)),
        state=sdk.StrategyState.empty(),
    )
    intent = sdk.ProtectPositionIntent(
        intent_id="protect_latest_visible",
        position_id=position.position_id,
        managed_exit=sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(distance=Decimal("1.5000"))
        ),
    )

    if valid:
        output = _validate_output(spec=spec, context=context, intents=(intent,))
        assert output.intents == (intent,)
    else:
        with pytest.raises(ValidationError):
            _validate_output(spec=spec, context=context, intents=(intent,))


def test_one_output_cannot_mutate_the_same_lifecycle_target_twice() -> None:
    spec = _spec(capabilities=frozenset({sdk.Capability.PLATFORM_TRAILING_STOP}))
    position = _position("position_1")
    new_plan_context = _context(spec, positions=(position,))
    duplicate_creations = (
        sdk.ProtectPositionIntent(
            intent_id="protect_first",
            position_id=position.position_id,
            managed_exit=sdk.ManagedExitPlan(
                trailing_stop=sdk.TrailingStop(distance=Decimal("0.0040"))
            ),
        ),
        sdk.ProtectPositionIntent(
            intent_id="protect_second",
            position_id=position.position_id,
            managed_exit=sdk.ManagedExitPlan(
                trailing_stop=sdk.TrailingStop(distance=Decimal("0.0030"))
            ),
        ),
    )
    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=new_plan_context, intents=duplicate_creations)

    existing_plan = sdk.ManagedExitPlanSnapshot(
        managed_exit_plan_id="managed-plan/opaque",
        position_id=position.position_id,
        managed_exit=sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(
                distance=Decimal("0.0040"), activation_price=Decimal("1.1100")
            )
        ),
        created_at=EVENT_TIME - timedelta(minutes=1),
    )
    existing_plan_context = _context(
        spec,
        positions=(position,),
        managed_exit_plans=(existing_plan,),
    )
    conflicting_mutations = (
        sdk.ModifyManagedExitIntent(
            intent_id="modify_plan",
            managed_exit_plan_id=existing_plan.managed_exit_plan_id,
            managed_exit=sdk.ManagedExitPlan(
                trailing_stop=sdk.TrailingStop(distance=Decimal("0.0030"))
            ),
        ),
        sdk.ClearManagedExitIntent(
            intent_id="clear_plan",
            managed_exit_plan_id=existing_plan.managed_exit_plan_id,
        ),
    )
    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=existing_plan_context, intents=conflicting_mutations)


@pytest.mark.parametrize(
    ("side", "declared_type"),
    [
        (sdk.PositionSide.BUY, sdk.OrderType.SELL),
        (sdk.PositionSide.SELL, sdk.OrderType.BUY),
    ],
)
def test_signal_direction_requires_a_compatible_declared_entry_side(
    side: sdk.PositionSide, declared_type: sdk.OrderType
) -> None:
    spec = _spec(order_types=frozenset({declared_type}))
    signal = sdk.SignalIntent(
        signal_id="directional_signal",
        rule_name="entry_rule",
        symbol=sdk.Symbol.EURUSD,
        side=side,
        reference_price=Decimal("1.1000"),
        stop_loss=Decimal("1.0900" if side is sdk.PositionSide.BUY else "1.1100"),
    )

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), signals=(signal,))


@pytest.mark.parametrize(
    ("side", "declared_pending_type", "required_close_type"),
    [
        (sdk.PositionSide.BUY, sdk.OrderType.SELL_LIMIT, sdk.OrderType.SELL),
        (sdk.PositionSide.SELL, sdk.OrderType.BUY_LIMIT, sdk.OrderType.BUY),
    ],
)
def test_close_position_requires_its_inferred_deal_order_type(
    side: sdk.PositionSide,
    declared_pending_type: sdk.OrderType,
    required_close_type: sdk.OrderType,
) -> None:
    position = _position(
        "position_1",
        side=side,
        stop_loss=Decimal("1.0900" if side is sdk.PositionSide.BUY else "1.1100"),
    )
    close = sdk.ClosePositionIntent(intent_id="close_position", position_id=position.position_id)
    without_deal = _spec(order_types=frozenset({declared_pending_type}))
    with pytest.raises(ValidationError):
        _validate_output(
            spec=without_deal,
            context=_context(without_deal, positions=(position,)),
            intents=(close,),
        )

    with_deal = _spec(order_types=frozenset({declared_pending_type, required_close_type}))
    output = _validate_output(
        spec=with_deal,
        context=_context(with_deal, positions=(position,)),
        intents=(close,),
    )
    assert output.intents == (close,)


def test_signal_requires_an_executable_declared_order_and_filling_pair() -> None:
    spec = _spec(
        order_types=frozenset({sdk.OrderType.BUY_LIMIT}),
        filling_policies=frozenset({sdk.OrderFilling.FOK}),
        capabilities=frozenset({sdk.Capability.FOK_FILLING, sdk.Capability.DEPTH_OF_MARKET}),
    )
    signal = _signal()

    with pytest.raises(ValidationError):
        _validate_output(spec=spec, context=_context(spec), signals=(signal,))


def test_close_position_requires_a_market_legal_declared_filling() -> None:
    spec = _spec(
        order_types=frozenset({sdk.OrderType.SELL}),
        filling_policies=frozenset({sdk.OrderFilling.BOC}),
        capabilities=frozenset({sdk.Capability.BOC_FILLING, sdk.Capability.DEPTH_OF_MARKET}),
    )
    position = _position("position_1", side=sdk.PositionSide.BUY)
    close = sdk.ClosePositionIntent(intent_id="close_position", position_id=position.position_id)

    with pytest.raises(ValidationError):
        _validate_output(
            spec=spec,
            context=_context(spec, positions=(position,)),
            intents=(close,),
        )


@pytest.mark.parametrize("protection_kind", ["native", "managed"])
def test_missing_symbol_data_never_disables_existing_position_protection(
    protection_kind: str,
) -> None:
    capabilities = (
        frozenset({sdk.Capability.PLATFORM_TRAILING_STOP})
        if protection_kind == "managed"
        else frozenset()
    )
    spec = _spec(
        symbols=(sdk.Symbol.EURUSD, sdk.Symbol.XAUUSD),
        capabilities=capabilities,
    )
    position = sdk.Position(
        position_id="xau_position",
        symbol=sdk.Symbol.XAUUSD,
        side=sdk.PositionSide.BUY,
        volume=Decimal("0.1"),
        average_price=Decimal("2400"),
        opened_at=EVENT_TIME - timedelta(minutes=5),
        stop_loss=Decimal("2390"),
    )
    context = _context(
        spec,
        present_symbols=(sdk.Symbol.EURUSD,),
        positions=(position,),
    )
    intent = (
        sdk.ProtectPositionIntent(
            intent_id="protect_native",
            position_id="xau_position",
            stop_loss=Decimal("2395"),
        )
        if protection_kind == "native"
        else sdk.ProtectPositionIntent(
            intent_id="protect_managed",
            position_id="xau_position",
            managed_exit=sdk.ManagedExitPlan(trailing_stop=sdk.TrailingStop(distance=Decimal("5"))),
        )
    )

    output = _validate_output(spec=spec, context=context, intents=(intent,))
    assert output.intents == (intent,)
