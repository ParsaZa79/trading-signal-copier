"""MT5-native order enums and platform-managed order contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import IntEnum
from typing import Annotated, Literal, Self, final

from pydantic import Field, field_validator, model_validator

from trading_strategy_sdk._model import (
    ContractModel,
    FiniteDecimal,
    Identifier,
    OpaqueId,
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


def validate_order_expiration(time: OrderTime, expires_at: datetime | None) -> None:
    """Validate the native expiration-field relationship."""
    if (time in _EXPIRING_ORDER_TIMES) != (expires_at is not None):
        raise ValueError("SPECIFIED order times require expires_at and other times forbid it")


def validate_pending_filling(order_type: OrderType, filling: OrderFilling) -> None:
    """Validate MT5 filling policies that are legal on a pending request."""
    if filling in {OrderFilling.FOK, OrderFilling.IOC}:
        raise ValueError("pending orders must use RETURN or a supported BOC filling policy")
    if filling is OrderFilling.BOC and order_type not in _BOC_ORDER_TYPES:
        raise ValueError("BOC is valid only for limit and stop-limit orders")


def pending_order_basis(
    order_type: OrderType,
    entry_price: Decimal,
    stop_limit_price: Decimal | None,
) -> Decimal:
    """Return the eventual entry basis after validating stop-limit geometry."""
    if order_type.is_stop_limit:
        if stop_limit_price is None:
            raise ValueError("stop-limit orders require stop_limit_price")
        if order_type is OrderType.BUY_STOP_LIMIT and stop_limit_price >= entry_price:
            raise ValueError("BUY stop-limit limit price must be below its trigger price")
        if order_type is OrderType.SELL_STOP_LIMIT and stop_limit_price <= entry_price:
            raise ValueError("SELL stop-limit limit price must be above its trigger price")
        return stop_limit_price
    if stop_limit_price is not None:
        raise ValueError("stop_limit_price is valid only for stop-limit orders")
    return entry_price


def validate_directional_protection(
    order_type: OrderType,
    basis: Decimal,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
    *,
    label: str,
) -> None:
    """Validate technical SL/TP direction from the eventual entry basis."""
    if order_type.is_buy:
        if stop_loss is not None and stop_loss >= basis:
            raise ValueError(f"BUY {label} stop loss must be below entry basis")
        if take_profit is not None and take_profit <= basis:
            raise ValueError(f"BUY {label} take profit must be above entry basis")
    else:
        if stop_loss is not None and stop_loss <= basis:
            raise ValueError(f"SELL {label} stop loss must be above entry basis")
        if take_profit is not None and take_profit >= basis:
            raise ValueError(f"SELL {label} take profit must be below entry basis")


def validate_pending_order_semantics(
    *,
    order_type: OrderType,
    entry_price: Decimal,
    stop_limit_price: Decimal | None,
    stop_loss: Decimal | None,
    take_profit: Decimal | None,
    filling: OrderFilling,
    time: OrderTime,
    expires_at: datetime | None,
    label: str = "entry",
    require_stop_loss: bool = True,
) -> Decimal:
    """Validate one fully materialized pending order and return its entry basis."""
    if not order_type.is_pending:
        raise ValueError(f"{label} must use a pending order type")
    basis = pending_order_basis(order_type, entry_price, stop_limit_price)
    validate_pending_filling(order_type, filling)
    validate_order_expiration(time, expires_at)
    if require_stop_loss and stop_loss is None:
        raise ValueError(f"{label} requires a technical stop loss")
    validate_directional_protection(
        order_type,
        basis,
        stop_loss,
        take_profit,
        label=label,
    )
    return basis


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

    @field_validator("partials")
    @classmethod
    def order_partials(cls, values: tuple[PartialExit, ...]) -> tuple[PartialExit, ...]:
        return tuple(sorted(values, key=lambda item: item.trigger_price))

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


def validate_managed_exit_direction(
    *,
    is_buy: bool,
    basis: Decimal,
    managed_exit: ManagedExitPlan,
    label: str = "managed exit",
    immediate_trailing_basis: Decimal | None = None,
) -> None:
    """Require profit-triggered managed actions to lie beyond the entry basis."""
    triggers: list[tuple[str, Decimal]] = []
    if managed_exit.trailing_stop is not None:
        activation = managed_exit.trailing_stop.activation_price
        if activation is not None:
            triggers.append(("trailing activation", activation))
    if managed_exit.break_even is not None:
        break_even = managed_exit.break_even
        triggers.append(("break-even trigger", break_even.trigger_price))
        resulting_stop = basis + break_even.offset
        if resulting_stop <= 0:
            raise ValueError(f"{label} break-even stop must remain positive")
        if is_buy and resulting_stop >= break_even.trigger_price:
            raise ValueError(f"BUY {label} break-even stop must remain below its trigger")
        if not is_buy and resulting_stop <= break_even.trigger_price:
            raise ValueError(f"SELL {label} break-even stop must remain above its trigger")
    if managed_exit.trailing_stop is not None:
        trailing = managed_exit.trailing_stop
        reference = (
            trailing.activation_price
            if trailing.activation_price is not None
            else immediate_trailing_basis
            if immediate_trailing_basis is not None
            else basis
        )
        if is_buy and reference - trailing.distance <= 0:
            raise ValueError(f"BUY {label} trailing stop must remain positive")
    triggers.extend(("partial-exit trigger", item.trigger_price) for item in managed_exit.partials)
    for trigger_name, trigger in triggers:
        if is_buy and trigger <= basis:
            raise ValueError(f"BUY {label} {trigger_name} must be above entry basis")
        if not is_buy and trigger >= basis:
            raise ValueError(f"SELL {label} {trigger_name} must be below entry basis")


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
    managed_exit: ManagedExitPlan | None = None
    filling: OrderFilling = OrderFilling.RETURN
    time: OrderTime = OrderTime.GTC
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def expiration_is_utc(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_native_parameters(self) -> Self:
        if self.bracket is not None and self.managed_exit is not None:
            raise ValueError("OCO leg cannot declare both bracket and managed_exit")
        managed_bracket = (
            self.managed_exit.bracket if self.managed_exit is not None else self.bracket
        )
        if managed_bracket is not None and (
            self.stop_loss is not None or self.take_profit is not None
        ):
            raise ValueError("native SL/TP cannot duplicate a managed bracket")

        stop_loss = managed_bracket.stop_loss if managed_bracket is not None else self.stop_loss
        take_profit = (
            managed_bracket.take_profit if managed_bracket is not None else self.take_profit
        )
        validate_pending_order_semantics(
            order_type=self.order_type,
            entry_price=self.entry_price,
            stop_limit_price=self.stop_limit_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            filling=self.filling,
            time=self.time,
            expires_at=self.expires_at,
            label="OCO entry leg",
        )
        return self


class OcoGroup(ContractModel):
    """At least two pending legs where a fill cancels the remaining legs."""

    group_id: Identifier
    legs: Annotated[tuple[OcoLeg, ...], Field(min_length=2)]

    @field_validator("legs")
    @classmethod
    def order_legs(cls, values: tuple[OcoLeg, ...]) -> tuple[OcoLeg, ...]:
        return tuple(sorted(values, key=lambda item: item.leg_id))

    @model_validator(mode="after")
    def validate_legs(self) -> Self:
        leg_ids = [leg.leg_id for leg in self.legs]
        if len(set(leg_ids)) != len(leg_ids):
            raise ValueError("OCO leg_id values must be unique")
        return self


@final
class PendingOrder(ContractModel):
    """Read-only technical snapshot of an active pending order."""

    order_id: OpaqueId
    symbol: Symbol
    order_type: OrderType
    entry_price: Price
    stop_limit_price: Price | None = None
    stop_loss: Price | None = None
    take_profit: Price | None = None
    filling: OrderFilling = OrderFilling.RETURN
    time: OrderTime = OrderTime.GTC
    expires_at: datetime | None = None
    placed_at: datetime
    oco_group_id: OpaqueId | None = None
    managed_exit_plan_id: OpaqueId | None = None

    @field_validator("expires_at")
    @classmethod
    def expiration_is_utc(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value is not None else None

    @field_validator("placed_at")
    @classmethod
    def placed_at_is_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        validate_pending_order_semantics(
            order_type=self.order_type,
            entry_price=self.entry_price,
            stop_limit_price=self.stop_limit_price,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            filling=self.filling,
            time=self.time,
            expires_at=self.expires_at,
            label="pending order snapshot",
            require_stop_loss=self.managed_exit_plan_id is None,
        )
        return self


@final
class OcoLegSnapshot(ContractModel):
    """Stable mapping from a declarative OCO leg to its active order ID."""

    leg_id: Identifier
    order_id: OpaqueId
    managed_exit_plan_id: OpaqueId | None = None


@final
class OcoGroupSnapshot(ContractModel):
    """Read-only identity snapshot for an active platform-managed OCO group."""

    oco_group_id: OpaqueId
    legs: Annotated[tuple[OcoLegSnapshot, ...], Field(min_length=2)]
    created_at: datetime

    @field_validator("legs")
    @classmethod
    def order_legs(cls, values: tuple[OcoLegSnapshot, ...]) -> tuple[OcoLegSnapshot, ...]:
        return tuple(sorted(values, key=lambda item: item.leg_id))

    @field_validator("created_at")
    @classmethod
    def created_at_is_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @model_validator(mode="after")
    def validate_legs(self) -> Self:
        leg_ids = [leg.leg_id for leg in self.legs]
        if len(set(leg_ids)) != len(leg_ids):
            raise ValueError("OCO snapshot leg_id values must be unique")
        order_ids = [leg.order_id for leg in self.legs]
        if len(set(order_ids)) != len(order_ids):
            raise ValueError("OCO snapshot order_id values must be unique")
        return self


@final
class ManagedExitPlanSnapshot(ContractModel):
    """Read-only platform-managed plan attached to one order or position."""

    managed_exit_plan_id: OpaqueId
    position_id: OpaqueId | None = None
    order_id: OpaqueId | None = None
    managed_exit: ManagedExitPlan
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_is_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @model_validator(mode="after")
    def has_exactly_one_target(self) -> Self:
        if (self.position_id is None) == (self.order_id is None):
            raise ValueError("managed exit plan snapshot requires exactly one target")
        return self


@final
class OrderPlacementResult(ContractModel):
    """Platform-issued IDs resulting from one order placement intent."""

    kind: Literal["order_placement_result"] = "order_placement_result"
    intent_id: Identifier
    order_id: OpaqueId
    managed_exit_plan_id: OpaqueId | None = None
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_is_utc(cls, value: datetime) -> datetime:
        return as_utc(value)


@final
class OcoLegPlacementResult(ContractModel):
    """Platform-issued IDs for one placed OCO leg."""

    leg_id: Identifier
    order_id: OpaqueId
    managed_exit_plan_id: OpaqueId | None = None


@final
class OcoPlacementResult(ContractModel):
    """Platform-issued group and order IDs resulting from OCO placement."""

    kind: Literal["oco_placement_result"] = "oco_placement_result"
    intent_id: Identifier
    oco_group_id: OpaqueId
    legs: Annotated[tuple[OcoLegPlacementResult, ...], Field(min_length=2)]
    created_at: datetime

    @field_validator("legs")
    @classmethod
    def order_legs(
        cls, values: tuple[OcoLegPlacementResult, ...]
    ) -> tuple[OcoLegPlacementResult, ...]:
        return tuple(sorted(values, key=lambda item: item.leg_id))

    @field_validator("created_at")
    @classmethod
    def created_at_is_utc(cls, value: datetime) -> datetime:
        return as_utc(value)

    @model_validator(mode="after")
    def validate_legs(self) -> Self:
        leg_ids = [leg.leg_id for leg in self.legs]
        if len(set(leg_ids)) != len(leg_ids):
            raise ValueError("OCO placement result leg_id values must be unique")
        order_ids = [leg.order_id for leg in self.legs]
        if len(set(order_ids)) != len(order_ids):
            raise ValueError("OCO placement result order_id values must be unique")
        plan_ids = [
            leg.managed_exit_plan_id for leg in self.legs if leg.managed_exit_plan_id is not None
        ]
        if len(set(plan_ids)) != len(plan_ids):
            raise ValueError("OCO placement result managed plan IDs must be unique")
        return self


type PlacementResult = Annotated[
    OrderPlacementResult | OcoPlacementResult,
    Field(discriminator="kind"),
]
