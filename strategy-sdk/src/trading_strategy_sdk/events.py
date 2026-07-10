"""Deterministic closed-bar event contracts."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator

from trading_strategy_sdk._model import ContractModel as _ContractModel
from trading_strategy_sdk.market import BarSubscription

Price = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]


def _as_utc(value: datetime) -> datetime:
    try:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("bar and event times must be timezone-aware UTC values")
        return value.astimezone(UTC)
    except Exception as error:
        raise ValueError(
            "bar and event times must be representable timezone-aware UTC values"
        ) from error


class OHLC(_ContractModel):
    """One side of a Bid/Ask OHLC bar."""

    open: Price
    high: Price
    low: Price
    close: Price

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if self.high < max(self.open, self.close) or self.low > min(self.open, self.close):
            raise ValueError("OHLC high/low must contain open and close")
        if self.low > self.high:
            raise ValueError("OHLC low cannot exceed high")
        return self


class ClosedBar(_ContractModel):
    """A complete canonical Bid/Ask bar."""

    subscription: BarSubscription
    open_time: datetime
    close_time: datetime
    bid: OHLC
    ask: OHLC
    tick_volume: Annotated[int, Field(ge=0)] | None = None

    @field_validator("open_time", "close_time")
    @classmethod
    def times_are_utc(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @model_validator(mode="after")
    def validate_bar(self) -> Self:
        if self.open_time >= self.close_time:
            raise ValueError("closed bar open_time must precede close_time")
        for component in ("open", "high", "low", "close"):
            if getattr(self.ask, component) < getattr(self.bid, component):
                raise ValueError("Ask OHLC values cannot be below Bid OHLC values")
        return self


class BarClosedEvent(_ContractModel):
    """A deterministic event emitted no earlier than its bar close."""

    event_time: datetime
    bar: ClosedBar

    @field_validator("event_time")
    @classmethod
    def event_time_is_utc(cls, value: datetime) -> datetime:
        return _as_utc(value)

    @model_validator(mode="after")
    def event_follows_close(self) -> Self:
        if self.bar.close_time > self.event_time:
            raise ValueError("bar close_time cannot be after event_time (lookahead)")
        return self

    @property
    def identity_key(self) -> tuple[datetime, str, int]:
        """Return the stable bar identity, independent of delayed delivery."""
        subscription = self.bar.subscription
        return (self.bar.close_time, subscription.symbol.value, subscription.timeframe.minutes)

    @property
    def sort_key(self) -> tuple[datetime, str, int]:
        """Return the deterministic event-ordering key."""
        return self.identity_key


def ordered_events(events: Iterable[BarClosedEvent]) -> tuple[BarClosedEvent, ...]:
    """Return events in canonical order, rejecting ambiguous duplicates."""
    materialized = tuple(events)
    keys = [event.sort_key for event in materialized]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate bar-close event key")
    return tuple(sorted(materialized, key=lambda event: event.sort_key))
