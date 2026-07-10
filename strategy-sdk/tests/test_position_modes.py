from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_strategy_sdk.positions import Position, PositionBook, PositionMode, PositionSide
from trading_strategy_sdk.spec import Symbol


def _position(position_id: str, side: PositionSide = PositionSide.BUY) -> Position:
    stop_loss = Decimal("1.0950") if side is PositionSide.BUY else Decimal("1.1050")
    take_profit = Decimal("1.1100") if side is PositionSide.BUY else Decimal("1.0900")
    return Position(
        position_id=position_id,
        symbol=Symbol.EURUSD,
        side=side,
        volume=Decimal("0.12"),
        average_price=Decimal("1.1000"),
        opened_at=datetime(2026, 7, 10, 12, 0, tzinfo=UTC),
        stop_loss=stop_loss,
        take_profit=take_profit,
        source_order_ids=(f"order_{position_id}",),
    )


def test_netting_book_allows_at_most_one_position_per_symbol() -> None:
    position = _position("net_1")
    book = PositionBook(mode=PositionMode.NETTING, positions=(position,))

    assert book.for_symbol(Symbol.EURUSD) == (position,)

    with pytest.raises(ValidationError, match="one position per symbol"):
        PositionBook(
            mode=PositionMode.NETTING,
            positions=(position, _position("net_2", PositionSide.SELL)),
        )


def test_hedging_book_allows_distinct_opposite_positions() -> None:
    buy = _position("hedge_buy")
    sell = _position("hedge_sell", PositionSide.SELL)

    book = PositionBook(mode=PositionMode.HEDGING, positions=(sell, buy))

    assert book.positions == (buy, sell)
    assert {position.side for position in book.for_symbol(Symbol.EURUSD)} == {
        PositionSide.BUY,
        PositionSide.SELL,
    }
    assert PositionBook.model_validate_json(book.model_dump_json()) == book


def test_position_ids_are_unique_in_every_mode() -> None:
    position = _position("same")

    with pytest.raises(ValidationError, match="position_id"):
        PositionBook(mode=PositionMode.HEDGING, positions=(position, position))


def test_position_snapshot_is_immutable_and_can_report_filled_volume() -> None:
    position = _position("immutable")

    assert position.volume == Decimal("0.12")
    with pytest.raises(ValidationError, match="frozen"):
        position.volume = Decimal("5")  # type: ignore[misc]


def test_position_times_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="UTC"):
        Position(
            position_id="naive",
            symbol=Symbol.EURUSD,
            side=PositionSide.BUY,
            volume=Decimal("0.1"),
            average_price=Decimal("1.1"),
            opened_at=datetime(2026, 7, 10, 12, 0),
        )


def test_open_position_can_report_break_even_or_profit_locking_stop() -> None:
    position = _position("profit_lock").model_copy(update={"stop_loss": Decimal("1.1050")})

    assert position.stop_loss == Decimal("1.1050")
