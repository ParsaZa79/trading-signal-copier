"""MT5-native order enums and platform-managed order contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import IntEnum
from typing import Annotated, Self

from pydantic import Field, field_validator, model_validator

from trading_strategy_sdk._model import (
    ContractModel,
    FiniteDecimal,
    Identifier,
    PositiveDecimal,
    Price,
    as_utc,
)
from trading_strategy_sdk.market import Symbol


class OrderType(IntEnum):
    """MT5 ``ENUM_ORDER_TYPE`` values."""

    BUY = 0
    SELL = 1
    BUY_LIMIT = 2
    SELL_LIMIT = 3
    BUY_STOP = 4
    SELL_STOP = 5
    BUY_STOP_LIMIT = 6
    SELL_STOP_LIMIT = 7
    CLOSE_BY = 8

    @property
    def is_market(self) -> bool:
        """Whether this is a market-side order type."""
        return self in {OrderType.BUY, OrderType.SELL}

    @property
    def is_pending(self) -> bool:
        """Whether this is a pending entry order type."""
        return self in _PENDING_ORDER_TYPES

    @property
    def is_stop_limit(self) -> bool:
        """Whether this order needs both trigger and limit prices."""
        return self in _STOP_LIMIT_ORDER_TYPES

    @property
    def is_buy(self) -> bool:
        """Whether this order opens or closes on the buy side."""
        return self in {
            OrderType.BUY,
            OrderType.BUY_LIMIT,
            OrderType.BUY_STOP,
            OrderType.BUY_STOP_LIMIT,
        }


class TradeAction(IntEnum):
    """MT5 ``ENUM_TRADE_REQUEST_ACTIONS`` values."""

    DEAL = 1
    PENDING = 5
    SLTP = 6
    MODIFY = 7
    REMOVE = 8
    CLOSE_BY = 10


class OrderTime(IntEnum):
    """MT5 ``ENUM_ORDER_TYPE_TIME`` values."""

    GTC = 0
    DAY = 1
    SPECIFIED = 2
    SPECIFIED_DAY = 3


class OrderFilling(IntEnum):
    """MT5 ``ENUM_ORDER_TYPE_FILLING`` values."""

    FOK = 0
    IOC = 1
    RETURN = 2
    BOC = 3


_PENDING_ORDER_TYPES = frozenset(
    {
        OrderType.BUY_LIMIT,
        OrderType.SELL_LIMIT,
        OrderType.BUY_STOP,
        OrderType.SELL_STOP,
        OrderType.BUY_STOP_LIMIT,
        OrderType.SELL_STOP_LIMIT,
    }
)
_STOP_LIMIT_ORDER_TYPES = frozenset({OrderType.BUY_STOP_LIMIT, OrderType.SELL_STOP_LIMIT})
_BOC_ORDER_TYPES = frozenset(
    {
        OrderType.BUY_LIMIT,
        OrderType.SELL_LIMIT,
        OrderType.BUY_STOP_LIMIT,
        OrderType.SELL_STOP_LIMIT,
    }
)
_EXPIRING_ORDER_TIMES = frozenset({OrderTime.SPECIFIED, OrderTime.SPECIFIED_DAY})


class BracketExit(ContractModel):
    """Platform-managed stop-loss and take-profit bracket."""

    stop_loss: Price
    take_profit: Price


class TrailingStop(ContractModel):
    """Platform-managed trailing stop expressed in price distance."""

    distance: PositiveDecimal
    activation_price: Price | None = None
    step: PositiveDecimal | None = None

    @model_validator(mode="after")
    def validate_step(self) -> Self:
        if self.step is not None and self.step > self.distance:
            raise ValueError("trailing step cannot exceed trailing distance")
        return self


class BreakEven(ContractModel):
    """Move protection to entry plus an optional signed technical offset."""

    trigger_price: Price
    offset: FiniteDecimal = Decimal(0)


class PartialExit(ContractModel):
    """Close a relative fraction of the initial position at a trigger price."""

    trigger_price: Price
    fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)]


class ManagedExitPlan(ContractModel):
    """Declarative platform-managed protective actions."""

    bracket: BracketExit | None = None
    trailing_stop: TrailingStop | None = None
    break_even: BreakEven | None = None
    partials: tuple[PartialExit, ...] = ()

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        if (
            self.bracket is None
            and self.trailing_stop is None
            and self.break_even is None
            and not self.partials
        ):
            raise ValueError("managed exit plan requires at least one action")
        total = sum((item.fraction for item in self.partials), start=Decimal(0))
        if total > 1:
            raise ValueError("cumulative partial-exit fraction cannot exceed one")
        triggers = [item.trigger_price for item in self.partials]
        if len(set(triggers)) != len(triggers):
            raise ValueError("partial-exit trigger prices must be unique")
        return self


class OcoLeg(ContractModel):
    """One technical pending-order leg in a platform-managed OCO group."""

    leg_id: Identifier
    symbol: Symbol
    order_type: OrderType
    entry_price: Price
    stop_limit_price: Price | None = None
    stop_loss: Price | None = None
    take_profit: Price | None = None
    bracket: BracketExit | None = None
    filling: OrderFilling = OrderFilling.RETURN
    time: OrderTime = OrderTime.GTC
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def expiration_is_utc(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_native_parameters(self) -> Self:
        if not self.order_type.is_pending:
            raise ValueError("OCO legs must use pending order types")
        if self.order_type.is_stop_limit and self.stop_limit_price is None:
            raise ValueError("stop-limit orders require stop_limit_price")
        if not self.order_type.is_stop_limit and self.stop_limit_price is not None:
            raise ValueError("stop_limit_price is valid only for stop-limit orders")
        if (self.time in _EXPIRING_ORDER_TIMES) != (self.expires_at is not None):
            raise ValueError("SPECIFIED order times require expires_at and other times forbid it")
        if self.filling is OrderFilling.BOC and self.order_type not in _BOC_ORDER_TYPES:
            raise ValueError("BOC is valid only for limit and stop-limit orders")
        if self.bracket is not None and (
            self.stop_loss is not None or self.take_profit is not None
        ):
            raise ValueError("native SL/TP cannot duplicate an OCO bracket")

        stop_loss = self.bracket.stop_loss if self.bracket is not None else self.stop_loss
        take_profit = self.bracket.take_profit if self.bracket is not None else self.take_profit
        if stop_loss is None:
            raise ValueError("OCO entry legs require a technical stop loss")
        if self.order_type.is_buy:
            if stop_loss >= self.entry_price:
                raise ValueError("BUY OCO stop loss must be below entry_price")
            if take_profit is not None and take_profit <= self.entry_price:
                raise ValueError("BUY OCO take profit must be above entry_price")
        else:
            if stop_loss <= self.entry_price:
                raise ValueError("SELL OCO stop loss must be above entry_price")
            if take_profit is not None and take_profit >= self.entry_price:
                raise ValueError("SELL OCO take profit must be below entry_price")
        return self


class OcoGroup(ContractModel):
    """At least two pending legs where a fill cancels the remaining legs."""

    group_id: Identifier
    legs: Annotated[tuple[OcoLeg, ...], Field(min_length=2)]

    @model_validator(mode="after")
    def validate_legs(self) -> Self:
        leg_ids = [leg.leg_id for leg in self.legs]
        if len(set(leg_ids)) != len(leg_ids):
            raise ValueError("OCO leg_id values must be unique")
        return self
