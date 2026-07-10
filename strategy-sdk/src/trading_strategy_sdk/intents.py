"""Strategy-emitted intents that exclude execution sizing and user risk policy."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self, final

from pydantic import Field, TypeAdapter, field_validator, model_validator

from trading_strategy_sdk._model import ContractModel, Identifier, OpaqueId, Price, as_utc
from trading_strategy_sdk.market import Symbol
from trading_strategy_sdk.orders import (
    ManagedExitPlan,
    OcoGroup,
    OrderFilling,
    OrderTime,
    OrderType,
    TradeAction,
)
from trading_strategy_sdk.positions import PositionSide

_EXPIRING_ORDER_TIMES = frozenset({OrderTime.SPECIFIED, OrderTime.SPECIFIED_DAY})
_BOC_ORDER_TYPES = frozenset(
    {
        OrderType.BUY_LIMIT,
        OrderType.SELL_LIMIT,
        OrderType.BUY_STOP_LIMIT,
        OrderType.SELL_STOP_LIMIT,
    }
)


@final
class SignalIntent(ContractModel):
    """A directional signal containing technical prices only."""

    kind: Literal["signal"] = "signal"
    signal_id: Identifier
    rule_name: Identifier
    symbol: Symbol
    side: PositionSide
    reference_price: Price
    stop_loss: Price
    take_profit: Price | None = None

    @model_validator(mode="after")
    def validate_price_direction(self) -> Self:
        if self.side is PositionSide.BUY:
            if self.stop_loss >= self.reference_price:
                raise ValueError("BUY signal stop_loss must be below reference_price")
            if self.take_profit is not None and self.take_profit <= self.reference_price:
                raise ValueError("BUY signal take_profit must be above reference_price")
        else:
            if self.stop_loss <= self.reference_price:
                raise ValueError("SELL signal stop_loss must be above reference_price")
            if self.take_profit is not None and self.take_profit >= self.reference_price:
                raise ValueError("SELL signal take_profit must be below reference_price")
        return self


class _OrderIntentModel(ContractModel):
    intent_id: Identifier


@final
class PlaceOrderIntent(_OrderIntentModel):
    """Request an entry without choosing final volume or an account."""

    kind: Literal["place_order"] = "place_order"
    symbol: Symbol
    order_type: OrderType
    entry_price: Price | None = None
    stop_limit_price: Price | None = None
    stop_loss: Price | None = None
    take_profit: Price | None = None
    filling: OrderFilling = OrderFilling.RETURN
    time: OrderTime = OrderTime.GTC
    expires_at: datetime | None = None
    managed_exit: ManagedExitPlan | None = None

    @field_validator("expires_at")
    @classmethod
    def expiration_is_utc(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_order_parameters(self) -> Self:
        if self.order_type is OrderType.CLOSE_BY:
            raise ValueError("CLOSE_BY must use CloseByIntent")
        if self.order_type.is_market:
            if self.entry_price is not None:
                raise ValueError("market order entry_price must be selected by the platform")
            if self.stop_limit_price is not None:
                raise ValueError("market orders cannot set stop_limit_price")
            if self.time is not OrderTime.GTC or self.expires_at is not None:
                raise ValueError("market orders cannot set pending-order expiration")
        else:
            if not self.order_type.is_pending:  # pragma: no cover - CLOSE_BY handled above
                raise ValueError("unsupported placement order type")
            if self.entry_price is None:
                raise ValueError("pending orders require entry_price")
            if self.order_type.is_stop_limit and self.stop_limit_price is None:
                raise ValueError("stop-limit orders require stop_limit_price")
            if not self.order_type.is_stop_limit and self.stop_limit_price is not None:
                raise ValueError("stop_limit_price is valid only for stop-limit orders")

        if (self.time in _EXPIRING_ORDER_TIMES) != (self.expires_at is not None):
            raise ValueError("SPECIFIED order times require expires_at and other times forbid it")
        if self.filling is OrderFilling.BOC and self.order_type not in _BOC_ORDER_TYPES:
            raise ValueError("BOC is valid only for limit and stop-limit orders")
        if (
            self.managed_exit is not None
            and self.managed_exit.bracket is not None
            and (self.stop_loss is not None or self.take_profit is not None)
        ):
            raise ValueError("native SL/TP cannot duplicate a managed bracket")

        bracket = self.managed_exit.bracket if self.managed_exit is not None else None
        stop_loss = bracket.stop_loss if bracket is not None else self.stop_loss
        take_profit = bracket.take_profit if bracket is not None else self.take_profit
        if stop_loss is None:
            raise ValueError("entry intents require a technical stop loss")
        if self.entry_price is not None:
            if self.order_type.is_buy:
                if stop_loss >= self.entry_price:
                    raise ValueError("BUY entry stop loss must be below entry_price")
                if take_profit is not None and take_profit <= self.entry_price:
                    raise ValueError("BUY entry take profit must be above entry_price")
            else:
                if stop_loss <= self.entry_price:
                    raise ValueError("SELL entry stop loss must be above entry_price")
                if take_profit is not None and take_profit >= self.entry_price:
                    raise ValueError("SELL entry take profit must be below entry_price")
        return self

    @property
    def action(self) -> TradeAction:
        """Return the corresponding native placement action."""
        return TradeAction.DEAL if self.order_type.is_market else TradeAction.PENDING


@final
class PlaceOcoIntent(_OrderIntentModel):
    """Request a platform-managed OCO group without any sizing fields."""

    kind: Literal["place_oco"] = "place_oco"
    group: OcoGroup

    @property
    def action(self) -> TradeAction:
        return TradeAction.PENDING


@final
class ModifyOrderIntent(_OrderIntentModel):
    """Modify technical fields on an existing pending order."""

    kind: Literal["modify_order"] = "modify_order"
    order_id: OpaqueId
    entry_price: Price | None = None
    stop_limit_price: Price | None = None
    stop_loss: Price | None = None
    take_profit: Price | None = None
    time: OrderTime | None = None
    expires_at: datetime | None = None
    clear_stop_loss: bool = False
    clear_take_profit: bool = False
    clear_expiration: bool = False

    @field_validator("expires_at")
    @classmethod
    def expiration_is_utc(cls, value: datetime | None) -> datetime | None:
        return as_utc(value) if value is not None else None

    @model_validator(mode="after")
    def require_a_change(self) -> Self:
        if all(
            value is None
            for value in (
                self.entry_price,
                self.stop_limit_price,
                self.stop_loss,
                self.take_profit,
                self.time,
                self.expires_at,
            )
        ) and not (self.clear_stop_loss or self.clear_take_profit or self.clear_expiration):
            raise ValueError("modify intent requires at least one technical change")
        if self.stop_loss is not None and self.clear_stop_loss:
            raise ValueError("modify intent cannot set and clear stop_loss")
        if self.take_profit is not None and self.clear_take_profit:
            raise ValueError("modify intent cannot set and clear take_profit")
        if self.expires_at is not None and self.clear_expiration:
            raise ValueError("modify intent cannot set and clear expiration")
        if self.time is not None:
            if self.time in _EXPIRING_ORDER_TIMES and self.expires_at is None:
                raise ValueError("SPECIFIED order times require expires_at")
            if self.time not in _EXPIRING_ORDER_TIMES and self.expires_at is not None:
                raise ValueError("GTC and DAY expiration updates cannot carry expires_at")
            if self.time in _EXPIRING_ORDER_TIMES and self.clear_expiration:
                raise ValueError("SPECIFIED order times cannot clear expiration")
        return self

    @property
    def action(self) -> TradeAction:
        return TradeAction.MODIFY


@final
class CancelOrderIntent(_OrderIntentModel):
    """Cancel one existing pending order."""

    kind: Literal["cancel_order"] = "cancel_order"
    order_id: OpaqueId

    @property
    def action(self) -> TradeAction:
        return TradeAction.REMOVE


@final
class ProtectPositionIntent(_OrderIntentModel):
    """Set technical protection on an existing position."""

    kind: Literal["protect_position"] = "protect_position"
    position_id: OpaqueId
    stop_loss: Price | None = None
    take_profit: Price | None = None
    managed_exit: ManagedExitPlan | None = None
    clear_stop_loss: bool = False
    clear_take_profit: bool = False

    @model_validator(mode="after")
    def require_protection(self) -> Self:
        if (
            self.stop_loss is None
            and self.take_profit is None
            and self.managed_exit is None
            and not self.clear_stop_loss
            and not self.clear_take_profit
        ):
            raise ValueError("protect intent requires at least one technical protection")
        if self.stop_loss is not None and self.clear_stop_loss:
            raise ValueError("protect intent cannot set and clear stop_loss")
        if self.take_profit is not None and self.clear_take_profit:
            raise ValueError("protect intent cannot set and clear take_profit")
        if (
            self.managed_exit is not None
            and self.managed_exit.bracket is not None
            and (self.clear_stop_loss or self.clear_take_profit)
        ):
            raise ValueError("managed bracket cannot set and clear protection")
        return self

    @property
    def action(self) -> TradeAction:
        return TradeAction.SLTP


@final
class ClosePositionIntent(_OrderIntentModel):
    """Close a relative fraction; the platform resolves it to final volume."""

    kind: Literal["close_position"] = "close_position"
    position_id: OpaqueId
    fraction: Annotated[Decimal, Field(gt=0, le=1, allow_inf_nan=False)] = Decimal(1)

    @property
    def action(self) -> TradeAction:
        return TradeAction.DEAL


@final
class CloseByIntent(_OrderIntentModel):
    """Close two distinct opposite hedged positions against each other."""

    kind: Literal["close_by"] = "close_by"
    position_id: OpaqueId
    opposite_position_id: OpaqueId

    @model_validator(mode="after")
    def positions_are_different(self) -> Self:
        if self.position_id == self.opposite_position_id:
            raise ValueError("close-by requires two different positions")
        return self

    @property
    def action(self) -> TradeAction:
        return TradeAction.CLOSE_BY


type OrderIntent = Annotated[
    PlaceOrderIntent
    | PlaceOcoIntent
    | ModifyOrderIntent
    | CancelOrderIntent
    | ProtectPositionIntent
    | ClosePositionIntent
    | CloseByIntent,
    Field(discriminator="kind"),
]

_ORDER_INTENT_ADAPTER: TypeAdapter[OrderIntent] = TypeAdapter(OrderIntent)


def validate_order_intent(value: object) -> OrderIntent:
    """Validate untrusted structured output against the closed intent union."""
    return _ORDER_INTENT_ADAPTER.validate_python(value)
