"""Immutable netting and hedging position snapshots."""

from __future__ import annotations

from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Self

from pydantic import field_validator, model_validator

from trading_strategy_sdk._model import (
    ContractModel,
    OpaqueId,
    Price,
    as_utc,
)
from trading_strategy_sdk.market import Symbol


class PositionMode(StrEnum):
    """Account position accounting chosen by an immutable strategy version."""

    NETTING = "netting"
    HEDGING = "hedging"


class PositionSide(IntEnum):
    """MT5 ``ENUM_POSITION_TYPE`` values."""

    BUY = 0
    SELL = 1


class Position(ContractModel):
    """Read-only filled-position state visible to a strategy."""

    position_id: OpaqueId
    symbol: Symbol
    side: PositionSide
    average_price: Price
    opened_at: datetime
    stop_loss: Price | None = None
    take_profit: Price | None = None
    source_order_ids: tuple[OpaqueId, ...] = ()

    @field_validator("opened_at")
    @classmethod
    def opened_at_is_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @field_validator("source_order_ids")
    @classmethod
    def source_order_ids_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("source_order_ids must be unique")
        return tuple(sorted(values))


class PositionBook(ContractModel):
    """A position snapshot validated against its immutable accounting mode."""

    mode: PositionMode
    positions: tuple[Position, ...] = ()

    @field_validator("positions")
    @classmethod
    def positions_are_canonical(cls, values: tuple[Position, ...]) -> tuple[Position, ...]:
        return tuple(sorted(values, key=lambda item: (item.opened_at, item.position_id)))

    @model_validator(mode="after")
    def validate_mode(self) -> Self:
        ids = [position.position_id for position in self.positions]
        if len(set(ids)) != len(ids):
            raise ValueError("position_id values must be unique")
        if self.mode is PositionMode.NETTING:
            symbols = [position.symbol for position in self.positions]
            if len(set(symbols)) != len(symbols):
                raise ValueError("netting mode allows at most one position per symbol")
        return self

    def for_symbol(self, symbol: Symbol) -> tuple[Position, ...]:
        """Return positions for one symbol in snapshot order."""
        return tuple(position for position in self.positions if position.symbol is symbol)
