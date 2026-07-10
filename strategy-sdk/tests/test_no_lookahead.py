from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from itertools import permutations

import pytest
from pydantic import ValidationError

from trading_strategy_sdk.context import BarSeries, EntryBlocker, StrategyContext
from trading_strategy_sdk.events import OHLC, BarClosedEvent, ClosedBar, ordered_events
from trading_strategy_sdk.positions import PositionBook, PositionMode
from trading_strategy_sdk.spec import (
    BarSubscription,
    Symbol,
    SynchronizationMode,
    SynchronizationSpec,
    Timeframe,
    TriggerSpec,
    WarmupRequirement,
)
from trading_strategy_sdk.state import StrategyState


def _ohlc(value: str) -> OHLC:
    price = Decimal(value)
    return OHLC(open=price, high=price + Decimal("0.0002"), low=price, close=price)


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
        ask=_ohlc(str(Decimal(value) + Decimal("0.0001"))),
    )


def _context(
    *,
    event_bar: ClosedBar,
    histories: tuple[BarSeries, ...],
    synchronized_bars: tuple[ClosedBar, ...],
    required_subscriptions: tuple[BarSubscription, ...],
    warmup_bars: int = 0,
    synchronization_mode: SynchronizationMode = SynchronizationMode.LATEST_CLOSED,
    event_time: datetime | None = None,
) -> StrategyContext:
    return StrategyContext(
        event=BarClosedEvent(event_time=event_time or event_bar.close_time, bar=event_bar),
        trigger=TriggerSpec(name="active_close", subscriptions=(event_bar.subscription,)),
        synchronization=SynchronizationSpec(
            mode=synchronization_mode,
            required_subscriptions=required_subscriptions,
        ),
        warmup=tuple(
            WarmupRequirement(subscription=subscription, bars=warmup_bars)
            for subscription in required_subscriptions
        ),
        histories=histories,
        synchronized_bars=synchronized_bars,
        position_mode=PositionMode.HEDGING,
        positions=PositionBook(mode=PositionMode.HEDGING),
        state=StrategyState.empty(),
    )


def test_context_accepts_bar_closing_exactly_at_event_time() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, event_time)

    context = _context(
        event_bar=current,
        histories=(BarSeries(subscription=subscription, bars=(current,)),),
        synchronized_bars=(current,),
        required_subscriptions=(subscription,),
    )

    assert context.entries_allowed
    assert context.history(subscription) == (current,)
    assert context.latest_bar(subscription) == current


def test_context_rejects_every_bar_after_event_time() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, event_time)
    future = _bar(subscription, event_time + timedelta(minutes=5), "1.1010")

    with pytest.raises(ValidationError, match="lookahead"):
        _context(
            event_bar=current,
            histories=(BarSeries(subscription=subscription, bars=(current, future)),),
            synchronized_bars=(current,),
            required_subscriptions=(subscription,),
        )


def test_event_order_is_independent_of_ingestion_order() -> None:
    event_time = datetime(2026, 7, 10, 12, 0, tzinfo=UTC)
    subscriptions = (
        BarSubscription(symbol=Symbol.XAUUSD, timeframe=Timeframe.M5),
        BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.H1),
        BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5),
    )
    events = tuple(
        BarClosedEvent(event_time=event_time, bar=_bar(subscription, event_time, "2"))
        for subscription in subscriptions
    )

    expected = tuple(event.sort_key for event in ordered_events(events))
    assert all(
        tuple(event.sort_key for event in ordered_events(candidate)) == expected
        for candidate in permutations(events)
    )
    assert [event.bar.subscription for event in ordered_events(events)] == [
        BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5),
        BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.H1),
        BarSubscription(symbol=Symbol.XAUUSD, timeframe=Timeframe.M5),
    ]


def test_context_collection_order_is_structural_not_ingestion_order() -> None:
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    eurusd = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    xauusd = BarSubscription(symbol=Symbol.XAUUSD, timeframe=Timeframe.M5)
    eurusd_bar = _bar(eurusd, event_time)
    xauusd_bar = _bar(xauusd, event_time, "2400")

    context = _context(
        event_bar=eurusd_bar,
        histories=(
            BarSeries(subscription=xauusd, bars=(xauusd_bar,)),
            BarSeries(subscription=eurusd, bars=(eurusd_bar,)),
        ),
        synchronized_bars=(xauusd_bar, eurusd_bar),
        required_subscriptions=(xauusd, eurusd),
    )

    expected = (eurusd, xauusd)
    assert tuple(series.subscription for series in context.histories) == expected
    assert tuple(bar.subscription for bar in context.synchronized_bars) == expected
    assert context.required_subscriptions == expected
    assert tuple(item.subscription for item in context.warmup) == expected


def test_incomplete_multisymbol_snapshot_blocks_only_new_entries() -> None:
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    eurusd = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    xauusd = BarSubscription(symbol=Symbol.XAUUSD, timeframe=Timeframe.M5)
    eurusd_bar = _bar(eurusd, event_time)
    xauusd_bar = _bar(xauusd, event_time, "2400")

    context = _context(
        event_bar=eurusd_bar,
        histories=(
            BarSeries(subscription=eurusd, bars=(eurusd_bar,)),
            BarSeries(subscription=xauusd, bars=(xauusd_bar,)),
        ),
        synchronized_bars=(eurusd_bar,),
        required_subscriptions=(eurusd, xauusd),
    )

    assert not context.entries_allowed
    assert context.protective_exits_allowed
    assert context.missing_subscriptions == (xauusd,)
    assert context.entry_blockers == (EntryBlocker.DATA_INCOMPLETE,)


def test_snapshot_bar_must_be_latest_materialized_bar() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    previous = _bar(subscription, event_time - timedelta(minutes=5), "1.0990")
    current = _bar(subscription, event_time)

    with pytest.raises(ValidationError, match="latest"):
        _context(
            event_bar=current,
            histories=(BarSeries(subscription=subscription, bars=(previous, current)),),
            synchronized_bars=(previous,),
            required_subscriptions=(subscription,),
        )


def test_warmup_readiness_participates_in_entry_gate() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, event_time)

    context = _context(
        event_bar=current,
        histories=(BarSeries(subscription=subscription, bars=(current,)),),
        synchronized_bars=(current,),
        required_subscriptions=(subscription,),
        warmup_bars=2,
    )

    assert not context.entries_allowed
    assert context.entry_blockers == (EntryBlocker.WARMUP_INCOMPLETE,)
    assert context.warmup_incomplete_subscriptions == (subscription,)


def test_exact_close_synchronization_rejects_a_stale_snapshot_bar() -> None:
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    eurusd = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    xauusd = BarSubscription(symbol=Symbol.XAUUSD, timeframe=Timeframe.M5)
    current = _bar(eurusd, event_time)
    stale = _bar(xauusd, event_time - timedelta(minutes=5), "2400")

    with pytest.raises(ValidationError, match="EXACT_CLOSE"):
        _context(
            event_bar=current,
            histories=(
                BarSeries(subscription=eurusd, bars=(current,)),
                BarSeries(subscription=xauusd, bars=(stale,)),
            ),
            synchronized_bars=(current, stale),
            required_subscriptions=(eurusd, xauusd),
            synchronization_mode=SynchronizationMode.EXACT_CLOSE,
        )


def test_exact_close_uses_bar_boundary_when_event_delivery_is_delayed() -> None:
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    eurusd = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    xauusd = BarSubscription(symbol=Symbol.XAUUSD, timeframe=Timeframe.M5)
    eurusd_bar = _bar(eurusd, close_time)
    xauusd_bar = _bar(xauusd, close_time, "2400")

    context = _context(
        event_bar=eurusd_bar,
        event_time=close_time + timedelta(seconds=1),
        histories=(
            BarSeries(subscription=eurusd, bars=(eurusd_bar,)),
            BarSeries(subscription=xauusd, bars=(xauusd_bar,)),
        ),
        synchronized_bars=(eurusd_bar, xauusd_bar),
        required_subscriptions=(eurusd, xauusd),
        synchronization_mode=SynchronizationMode.EXACT_CLOSE,
    )

    assert context.entries_allowed


def test_context_exposes_positions_and_serializes_state_as_data() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, event_time)
    context = _context(
        event_bar=current,
        histories=(BarSeries(subscription=subscription, bars=(current,)),),
        synchronized_bars=(current,),
        required_subscriptions=(subscription,),
    ).model_copy(update={"state": StrategyState.from_mapping({"armed": True})})

    assert context.positions.mode is PositionMode.HEDGING
    assert '"state":{"armed":true}' in context.model_dump_json()
    assert StrategyContext.model_validate_json(context.model_dump_json()) == context


def test_validated_copy_cannot_add_future_history() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    current = _bar(subscription, event_time)
    future = _bar(subscription, event_time + timedelta(minutes=5), "1.1010")
    context = _context(
        event_bar=current,
        histories=(BarSeries(subscription=subscription, bars=(current,)),),
        synchronized_bars=(current,),
        required_subscriptions=(subscription,),
    )

    with pytest.raises(ValidationError, match="lookahead"):
        context.model_copy(
            update={"histories": (BarSeries(subscription=subscription, bars=(current, future)),)}
        )


def test_state_is_explicit_canonical_and_json_round_trippable() -> None:
    state = StrategyState.from_mapping(
        {"window": [3, 2, 1], "flags": {"armed": True}, "last_signal": None}
    )

    assert state.to_json() == ('{"flags":{"armed":true},"last_signal":null,"window":[3,2,1]}')
    assert StrategyState.from_json(state.to_json()) == state
    assert state.with_value("count", 2).to_mapping()["count"] == 2
    assert "count" not in state.to_mapping()


@pytest.mark.parametrize(
    "bad_state",
    [
        {"not_finite": float("nan")},
        {"timestamp": datetime(2026, 7, 10, tzinfo=UTC)},
        {"opaque": object()},
        {1: "non-string key"},
    ],
)
def test_state_rejects_values_that_are_not_portable_json(bad_state: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        StrategyState.from_mapping(bad_state)  # type: ignore[arg-type]


def test_bars_require_aware_times_and_monotonic_history() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    event_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    previous = _bar(subscription, event_time - timedelta(minutes=5), "1.0990")
    current = _bar(subscription, event_time)

    with pytest.raises(ValidationError, match="UTC"):
        _bar(subscription, event_time.replace(tzinfo=None))

    with pytest.raises(ValidationError, match="strictly ordered"):
        BarSeries(subscription=subscription, bars=(current, previous))
