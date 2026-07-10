from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_strategy_sdk.context import BarSeries, StrategyContext
from trading_strategy_sdk.events import OHLC, BarClosedEvent, ClosedBar
from trading_strategy_sdk.intents import (
    ClosePositionIntent,
    PlaceOcoIntent,
    PlaceOrderIntent,
    ProtectPositionIntent,
    SignalIntent,
)
from trading_strategy_sdk.market import BarSubscription, Symbol, Timeframe
from trading_strategy_sdk.orders import OcoGroup, OcoLeg, OrderFilling, OrderType
from trading_strategy_sdk.positions import Position, PositionBook, PositionMode, PositionSide
from trading_strategy_sdk.spec import (
    BoundedLossSpec,
    Capability,
    RuleSpec,
    StrategySpec,
    SynchronizationMode,
    SynchronizationSpec,
    TriggerSpec,
    WarmupRequirement,
)
from trading_strategy_sdk.state import StrategyState


def _ohlc(value: str) -> OHLC:
    price = Decimal(value)
    return OHLC(open=price, high=price, low=price, close=price)


def _bar(
    subscription: BarSubscription,
    close_time: datetime,
    value: str = "1.1000",
) -> ClosedBar:
    return ClosedBar(
        subscription=subscription,
        open_time=close_time - timedelta(minutes=subscription.timeframe.minutes),
        close_time=close_time,
        bid=_ohlc(value),
        ask=_ohlc(value),
    )


def _position(
    *,
    position_id: str,
    symbol: Symbol,
    opened_at: datetime,
    side: PositionSide = PositionSide.BUY,
) -> Position:
    return Position(
        position_id=position_id,
        symbol=symbol,
        side=side,
        average_price=Decimal("1.1000"),
        opened_at=opened_at,
        stop_loss=Decimal("1.0900") if side is PositionSide.BUY else Decimal("1.1100"),
    )


def _context(
    *,
    event_bar: ClosedBar,
    required_subscriptions: tuple[BarSubscription, ...],
    histories: tuple[BarSeries, ...],
    synchronized_bars: tuple[ClosedBar, ...],
    warmup_bars: int = 0,
    event_time: datetime | None = None,
    position_mode: PositionMode = PositionMode.HEDGING,
    positions: PositionBook | None = None,
) -> StrategyContext:
    return StrategyContext(
        event=BarClosedEvent(event_time=event_time or event_bar.close_time, bar=event_bar),
        trigger=TriggerSpec(name="active_close", subscriptions=(event_bar.subscription,)),
        synchronization=SynchronizationSpec(
            mode=SynchronizationMode.LATEST_CLOSED,
            required_subscriptions=required_subscriptions,
        ),
        warmup=tuple(
            WarmupRequirement(subscription=subscription, bars=warmup_bars)
            for subscription in required_subscriptions
        ),
        histories=histories,
        synchronized_bars=synchronized_bars,
        position_mode=position_mode,
        positions=positions or PositionBook(mode=position_mode),
        state=StrategyState.empty(),
    )


def _spec(context: StrategyContext) -> StrategySpec:
    subscriptions = context.required_subscriptions
    capabilities = {Capability.RETURN_FILLING, Capability.PLATFORM_OCO}
    if len({item.symbol for item in subscriptions}) > 1:
        capabilities.add(Capability.MULTI_SYMBOL_DATA)
    if len({item.timeframe for item in subscriptions}) > 1:
        capabilities.add(Capability.MULTI_TIMEFRAME_DATA)
    return StrategySpec(
        subscriptions=subscriptions,
        warmup=context.warmup,
        triggers=(context.trigger,),
        synchronization=context.synchronization,
        entries=(RuleSpec(name="trend_entry", description="Enter with the trend."),),
        exits=(RuleSpec(name="protective_exit", description="Protect or exit."),),
        position_mode=context.position_mode,
        required_capabilities=frozenset(capabilities),
        order_types=frozenset(
            {OrderType.BUY_LIMIT, OrderType.BUY_STOP, OrderType.SELL, OrderType.SELL_STOP}
        ),
        filling_policies=frozenset({OrderFilling.RETURN}),
        disclosures=("Market gaps can exceed a technical stop.",),
        bounded_loss=BoundedLossSpec(
            stop_loss_required=True,
            gap_risk_disclosed=True,
            description="Every entry carries technical protection.",
        ),
    )


def test_delayed_delivery_does_not_move_the_context_lookahead_boundary() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, close_time)
    future = _bar(subscription, close_time + timedelta(minutes=5), "1.1010")

    with pytest.raises(ValidationError, match=r"bar.*after.*event.*close|lookahead"):
        _context(
            event_bar=current,
            event_time=close_time + timedelta(minutes=10),
            required_subscriptions=(subscription,),
            histories=(BarSeries(subscription=subscription, bars=(current, future)),),
            synchronized_bars=(future,),
        )


def test_context_rejects_a_position_opened_after_the_event_bar_closed() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, close_time)
    future_position = _position(
        position_id="future",
        symbol=subscription.symbol,
        opened_at=close_time + timedelta(seconds=1),
    )

    with pytest.raises(ValidationError, match=r"position.*after.*event.*close|future position"):
        _context(
            event_bar=current,
            event_time=close_time + timedelta(minutes=1),
            required_subscriptions=(subscription,),
            histories=(BarSeries(subscription=subscription, bars=(current,)),),
            synchronized_bars=(current,),
            positions=PositionBook(mode=PositionMode.HEDGING, positions=(future_position,)),
        )


def test_context_rejects_positions_outside_the_declared_symbol_scope() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, close_time)
    unrelated = _position(
        position_id="other_strategy",
        symbol=Symbol.XAUUSD,
        opened_at=close_time - timedelta(minutes=1),
    )

    with pytest.raises(ValidationError, match="outside strategy symbol scope"):
        _context(
            event_bar=current,
            required_subscriptions=(subscription,),
            histories=(BarSeries(subscription=subscription, bars=(current,)),),
            synchronized_bars=(current,),
            positions=PositionBook(mode=PositionMode.HEDGING, positions=(unrelated,)),
        )


def test_context_position_book_must_use_the_declared_position_mode() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, close_time)

    with pytest.raises(ValidationError, match=r"position.*mode.*match"):
        _context(
            event_bar=current,
            required_subscriptions=(subscription,),
            histories=(BarSeries(subscription=subscription, bars=(current,)),),
            synchronized_bars=(current,),
            position_mode=PositionMode.HEDGING,
            positions=PositionBook(mode=PositionMode.NETTING),
        )


@pytest.mark.parametrize(
    ("timeframe", "lag"),
    [
        (Timeframe.M5, timedelta(minutes=5)),
        (Timeframe.H1, timedelta(hours=1)),
        (Timeframe.D1, timedelta(days=1)),
    ],
)
def test_latest_closed_snapshot_blocks_entries_at_the_stale_boundary(
    timeframe: Timeframe,
    lag: timedelta,
) -> None:
    import trading_strategy_sdk as sdk

    event_subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    other_subscription = BarSubscription(symbol=Symbol.XAUUSD, timeframe=timeframe)
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(event_subscription, close_time)
    stale = _bar(other_subscription, close_time - lag, "2400")

    context = _context(
        event_bar=current,
        required_subscriptions=(event_subscription, other_subscription),
        histories=(
            BarSeries(subscription=event_subscription, bars=(current,)),
            BarSeries(subscription=other_subscription, bars=(stale,)),
        ),
        synchronized_bars=(current, stale),
    )

    assert not context.entries_allowed
    assert context.entry_blockers == (sdk.EntryBlocker.DATA_STALE,)


@pytest.mark.parametrize(
    ("timeframe", "lag"),
    [
        (Timeframe.M5, timedelta(minutes=4, seconds=59)),
        (Timeframe.H1, timedelta(minutes=59, seconds=59)),
        (Timeframe.D1, timedelta(hours=23, minutes=59, seconds=59)),
    ],
)
def test_latest_closed_snapshot_accepts_a_fresh_slower_subscription(
    timeframe: Timeframe,
    lag: timedelta,
) -> None:
    event_subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    other_subscription = BarSubscription(symbol=Symbol.XAUUSD, timeframe=timeframe)
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(event_subscription, close_time)
    latest = _bar(other_subscription, close_time - lag, "2400")

    context = _context(
        event_bar=current,
        required_subscriptions=(event_subscription, other_subscription),
        histories=(
            BarSeries(subscription=event_subscription, bars=(current,)),
            BarSeries(subscription=other_subscription, bars=(latest,)),
        ),
        synchronized_bars=(current, latest),
    )

    assert context.entries_allowed
    assert not context.entry_blockers


@pytest.mark.parametrize(
    ("monthly_close", "event_close", "expected_stale"),
    [
        (
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 31, 23, 59, 59, tzinfo=UTC),
            False,
        ),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC), True),
        (
            datetime(2024, 2, 1, tzinfo=UTC),
            datetime(2024, 2, 29, 23, 59, 59, tzinfo=UTC),
            False,
        ),
        (datetime(2024, 2, 1, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC), True),
    ],
)
def test_latest_closed_monthly_freshness_uses_calendar_boundaries(
    monthly_close: datetime, event_close: datetime, expected_stale: bool
) -> None:
    event_subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    monthly_subscription = BarSubscription(symbol=Symbol.XAUUSD, timeframe=Timeframe.MN1)
    event_bar = _bar(event_subscription, event_close)
    monthly_bar = _bar(monthly_subscription, monthly_close, "2400")
    context = _context(
        event_bar=event_bar,
        required_subscriptions=(event_subscription, monthly_subscription),
        histories=(
            BarSeries(subscription=event_subscription, bars=(event_bar,)),
            BarSeries(subscription=monthly_subscription, bars=(monthly_bar,)),
        ),
        synchronized_bars=(event_bar, monthly_bar),
    )

    assert bool(context.stale_subscriptions) is expected_stale


def test_staleness_at_datetime_max_never_escapes_overflow() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    current = _bar(subscription, datetime.max.replace(tzinfo=UTC))
    context = _context(
        event_bar=current,
        required_subscriptions=(subscription,),
        histories=(BarSeries(subscription=subscription, bars=(current,)),),
        synchronized_bars=(current,),
    )

    assert context.entries_allowed


def _blocked_context(kind: str, *, with_position: bool = False) -> StrategyContext:
    event_subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    other_subscription = BarSubscription(symbol=Symbol.XAUUSD, timeframe=Timeframe.M5)
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    event_bar = _bar(event_subscription, close_time)
    other_bar = _bar(other_subscription, close_time, "2400")
    required = (event_subscription,)
    histories = (BarSeries(subscription=event_subscription, bars=(event_bar,)),)
    synchronized = (event_bar,)
    warmup_bars = 0
    if kind == "missing":
        required = (event_subscription, other_subscription)
        histories += (BarSeries(subscription=other_subscription, bars=(other_bar,)),)
    elif kind == "warmup":
        warmup_bars = 2
    elif kind == "stale":
        required = (event_subscription, other_subscription)
        stale = _bar(other_subscription, close_time - timedelta(minutes=5), "2400")
        histories += (BarSeries(subscription=other_subscription, bars=(stale,)),)
        synchronized += (stale,)
    else:
        raise AssertionError(f"unknown blocker kind: {kind}")

    positions = PositionBook(mode=PositionMode.HEDGING)
    if with_position:
        positions = PositionBook(
            mode=PositionMode.HEDGING,
            positions=(
                _position(
                    position_id="existing",
                    symbol=event_subscription.symbol,
                    opened_at=close_time - timedelta(minutes=1),
                ),
            ),
        )
    return _context(
        event_bar=event_bar,
        required_subscriptions=required,
        histories=histories,
        synchronized_bars=synchronized,
        warmup_bars=warmup_bars,
        positions=positions,
    )


def _entry_output(kind: str, symbol: Symbol) -> object:
    import trading_strategy_sdk as sdk

    signal = SignalIntent(
        signal_id="entry_signal",
        rule_name="trend_entry",
        symbol=symbol,
        side=PositionSide.BUY,
        reference_price=Decimal("1.1000"),
        stop_loss=Decimal("1.0900"),
    )
    if kind == "signal":
        return sdk.StrategyOutput(signals=(signal,), intents=(), next_state=StrategyState.empty())
    if kind == "order":
        order = PlaceOrderIntent(
            intent_id="entry_order",
            symbol=symbol,
            order_type=OrderType.BUY_LIMIT,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0900"),
        )
        return sdk.StrategyOutput(signals=(), intents=(order,), next_state=StrategyState.empty())
    buy = OcoLeg(
        leg_id="buy_breakout",
        symbol=symbol,
        order_type=OrderType.BUY_STOP,
        entry_price=Decimal("1.1100"),
        stop_loss=Decimal("1.0900"),
    )
    sell = OcoLeg(
        leg_id="sell_breakout",
        symbol=symbol,
        order_type=OrderType.SELL_STOP,
        entry_price=Decimal("1.0900"),
        stop_loss=Decimal("1.1100"),
    )
    oco = PlaceOcoIntent(
        intent_id="entry_oco",
        group=OcoGroup(group_id="breakout", legs=(buy, sell)),
    )
    return sdk.StrategyOutput(signals=(), intents=(oco,), next_state=StrategyState.empty())


@pytest.mark.parametrize("blocker_kind", ["missing", "warmup", "stale"])
@pytest.mark.parametrize("entry_kind", ["signal", "order", "oco"])
def test_context_aware_output_validation_enforces_every_entry_blocker(
    blocker_kind: str,
    entry_kind: str,
) -> None:
    import trading_strategy_sdk as sdk

    context = _blocked_context(blocker_kind)
    spec = _spec(context)
    output = _entry_output(entry_kind, context.event.bar.subscription.symbol)

    with pytest.raises(ValidationError, match=r"entr(?:y|ies).*(?:blocked|blocker)"):
        sdk.validate_strategy_output(output, spec=spec, context=context)


def test_output_validation_binds_the_specs_exact_warmup_requirements() -> None:
    import trading_strategy_sdk as sdk

    context = _ready_context()
    subscription = context.required_subscriptions[0]
    spec = _spec(context).model_copy(
        update={
            "warmup": (WarmupRequirement(subscription=subscription, bars=2),),
        }
    )
    weakened_context = context.model_copy(
        update={
            "warmup": (WarmupRequirement(subscription=subscription, bars=0),),
        }
    )

    with pytest.raises(ValidationError, match="warmup"):
        sdk.validate_strategy_output(
            _entry_output("order", Symbol.EURUSD),
            spec=spec,
            context=weakened_context,
        )


@pytest.mark.parametrize("blocker_kind", ["missing", "warmup", "stale"])
@pytest.mark.parametrize("intent_kind", ["protect", "close"])
def test_entry_blockers_do_not_disable_protective_or_exit_intents(
    blocker_kind: str,
    intent_kind: str,
) -> None:
    import trading_strategy_sdk as sdk

    context = _blocked_context(blocker_kind, with_position=True)
    spec = _spec(context)
    intent = (
        ProtectPositionIntent(
            intent_id="protect",
            position_id="existing",
            stop_loss=Decimal("1.0950"),
        )
        if intent_kind == "protect"
        else ClosePositionIntent(intent_id="close", position_id="existing")
    )
    output = sdk.StrategyOutput(
        signals=(),
        intents=(intent,),
        next_state=StrategyState.from_mapping({"protected": True}),
    )

    assert sdk.validate_strategy_output(output, spec=spec, context=context) == output


def _ready_context() -> StrategyContext:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, close_time)
    return _context(
        event_bar=current,
        required_subscriptions=(subscription,),
        histories=(BarSeries(subscription=subscription, bars=(current,)),),
        synchronized_bars=(current,),
    )


def test_strategy_output_is_closed_typed_and_json_round_trippable() -> None:
    import trading_strategy_sdk as sdk

    context = _ready_context()
    signal = SignalIntent(
        signal_id="entry_signal",
        rule_name="trend_entry",
        symbol=Symbol.EURUSD,
        side=PositionSide.BUY,
        reference_price=Decimal("1.1000"),
        stop_loss=Decimal("1.0900"),
    )
    order = PlaceOrderIntent(
        intent_id="entry_order",
        symbol=Symbol.EURUSD,
        order_type=OrderType.BUY_LIMIT,
        entry_price=Decimal("1.1000"),
        stop_loss=Decimal("1.0900"),
    )
    output = sdk.StrategyOutput(
        signals=(signal,),
        intents=(order,),
        next_state=StrategyState.from_mapping({"armed": True}),
    )

    assert sdk.StrategyOutput.model_validate_json(output.model_dump_json()) == output
    assert sdk.validate_strategy_output(output, spec=_spec(context), context=context) == output


def test_strategy_output_rejects_unknown_fields_and_hides_input() -> None:
    import trading_strategy_sdk as sdk

    context = _ready_context()
    secret = "DO-NOT-ECHO-OUTPUT-SECRET"
    payload = {"signals": [], "intents": [], "next_state": {}, "credentials": secret}

    with pytest.raises(ValidationError) as error:
        sdk.validate_strategy_output(payload, spec=_spec(context), context=context)
    assert secret not in str(error.value)


def test_strategy_output_rejects_unknown_intent_variants() -> None:
    import trading_strategy_sdk as sdk

    with pytest.raises(ValidationError):
        sdk.StrategyOutput.model_validate(
            {
                "signals": [],
                "intents": [{"kind": "run_arbitrary_order", "intent_id": "bad"}],
                "next_state": {},
            }
        )


def test_strategy_output_validation_schema_is_closed_and_bounded() -> None:
    import trading_strategy_sdk as sdk

    schema = sdk.StrategyOutput.model_json_schema(mode="validation")
    assert schema["additionalProperties"] is False
    properties = schema["properties"]
    assert properties["signals"]["maxItems"] == 256
    assert properties["intents"]["maxItems"] == 256


@pytest.mark.parametrize("collection", ["signals", "intents"])
def test_strategy_output_collections_have_a_finite_item_bound(collection: str) -> None:
    import trading_strategy_sdk as sdk

    if collection == "signals":
        items = tuple(
            SignalIntent(
                signal_id=f"signal_{index}",
                rule_name="trend_entry",
                symbol=Symbol.EURUSD,
                side=PositionSide.BUY,
                reference_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0900"),
            )
            for index in range(257)
        )
    else:
        items = tuple(
            PlaceOrderIntent(
                intent_id=f"order_{index}",
                symbol=Symbol.EURUSD,
                order_type=OrderType.BUY_LIMIT,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0900"),
            )
            for index in range(257)
        )
    values = {
        "signals": items if collection == "signals" else (),
        "intents": items if collection == "intents" else (),
        "next_state": StrategyState.empty(),
    }

    with pytest.raises(ValidationError):
        sdk.StrategyOutput.model_validate(values)


def test_strategy_output_bounds_invalid_iterables_before_consuming_them_all() -> None:
    import trading_strategy_sdk as sdk

    class CountingIterable:
        consumed = 0

        def __iter__(self) -> object:
            for index in range(10_000):
                self.consumed += 1
                yield {"signal_id": f"invalid_{index}"}

    values = CountingIterable()
    with pytest.raises(ValidationError):
        sdk.StrategyOutput.model_validate({"signals": values, "intents": (), "next_state": {}})
    assert values.consumed <= 257

    class LyingList(list[object]):
        def __len__(self) -> int:
            return 0

    with pytest.raises(ValidationError):
        sdk.StrategyOutput.model_validate(
            {
                "signals": LyingList({"signal_id": f"bad_{index}"} for index in range(1_000)),
                "intents": (),
                "next_state": {},
            }
        )


@pytest.mark.parametrize("collection", ["signals", "intents"])
def test_strategy_output_ids_are_unique_within_each_collection(collection: str) -> None:
    import trading_strategy_sdk as sdk

    if collection == "signals":
        item = SignalIntent(
            signal_id="duplicate",
            rule_name="trend_entry",
            symbol=Symbol.EURUSD,
            side=PositionSide.BUY,
            reference_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0900"),
        )
    else:
        item = PlaceOrderIntent(
            intent_id="duplicate",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY_LIMIT,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0900"),
        )
    values = {
        "signals": (item, item) if collection == "signals" else (),
        "intents": (item, item) if collection == "intents" else (),
        "next_state": StrategyState.empty(),
    }

    with pytest.raises(ValidationError, match="unique"):
        sdk.StrategyOutput.model_validate(values)
