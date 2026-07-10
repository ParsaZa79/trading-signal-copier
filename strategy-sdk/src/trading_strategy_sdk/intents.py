"""Strategy-emitted intents that exclude execution sizing and user risk policy."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Literal, Self, cast, final

from pydantic import (
    BeforeValidator,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

from trading_strategy_sdk._model import (
    ContractModel,
    Identifier,
    OpaqueId,
    Price,
    as_utc,
    has_plain_bounded_validation_containers,
)
from trading_strategy_sdk.market import Symbol
from trading_strategy_sdk.orders import (
    ManagedExitPlan,
    OcoGroup,
    OrderFilling,
    OrderTime,
    OrderType,
    TradeAction,
    validate_pending_order_semantics,
)
from trading_strategy_sdk.positions import PositionSide

if TYPE_CHECKING:
    from trading_strategy_sdk.context import StrategyContext
    from trading_strategy_sdk.spec import StrategySpec

_EXPIRING_ORDER_TIMES = frozenset({OrderTime.SPECIFIED, OrderTime.SPECIFIED_DAY})


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
            if self.filling is OrderFilling.BOC:
                raise ValueError("BOC is valid only for limit and stop-limit orders")
        elif not self.order_type.is_pending:  # pragma: no cover - CLOSE_BY handled above
            raise ValueError("unsupported placement order type")
        elif self.entry_price is None:
            raise ValueError("pending orders require entry_price")

        bracket = self.managed_exit.bracket if self.managed_exit is not None else None
        if bracket is not None and (self.stop_loss is not None or self.take_profit is not None):
            raise ValueError("native SL/TP cannot duplicate a managed bracket")
        stop_loss = bracket.stop_loss if bracket is not None else self.stop_loss
        take_profit = bracket.take_profit if bracket is not None else self.take_profit
        if stop_loss is None:
            raise ValueError("entry intents require a technical stop loss")
        if self.order_type.is_market:
            return self

        assert self.entry_price is not None  # narrowed by the pending-order branch above
        validate_pending_order_semantics(
            order_type=self.order_type,
            entry_price=self.entry_price,
            stop_limit_price=self.stop_limit_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            filling=self.filling,
            time=self.time,
            expires_at=self.expires_at,
            label="entry",
        )
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
    def action(self) -> None:
        """OCO expands to multiple platform-managed native requests."""
        return None


@final
class ModifyOcoIntent(_OrderIntentModel):
    """Atomically replace the technical definition of an active OCO group."""

    kind: Literal["modify_oco"] = "modify_oco"
    oco_group_id: OpaqueId
    group: OcoGroup

    @property
    def action(self) -> None:
        """A managed group modification has no single native action."""
        return None


@final
class CancelOcoIntent(_OrderIntentModel):
    """Cancel every remaining order in one active OCO group."""

    kind: Literal["cancel_oco"] = "cancel_oco"
    oco_group_id: OpaqueId

    @property
    def action(self) -> None:
        """A managed group cancellation has no single native action."""
        return None


@final
class ModifyManagedExitIntent(_OrderIntentModel):
    """Replace one active platform-managed exit plan."""

    kind: Literal["modify_managed_exit"] = "modify_managed_exit"
    managed_exit_plan_id: OpaqueId
    managed_exit: ManagedExitPlan

    @property
    def action(self) -> None:
        """A managed plan replacement has no single native action."""
        return None


@final
class ClearManagedExitIntent(_OrderIntentModel):
    """Clear one managed exit plan when bounded protection remains."""

    kind: Literal["clear_managed_exit"] = "clear_managed_exit"
    managed_exit_plan_id: OpaqueId

    @property
    def action(self) -> None:
        """A managed plan removal has no single native action."""
        return None


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
        ) and not (self.clear_take_profit or self.clear_expiration):
            raise ValueError("modify intent requires at least one technical change")
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
    clear_take_profit: bool = False

    @model_validator(mode="after")
    def require_protection(self) -> Self:
        if (
            self.stop_loss is None
            and self.take_profit is None
            and self.managed_exit is None
            and not self.clear_take_profit
        ):
            raise ValueError("protect intent requires at least one technical protection")
        if self.take_profit is not None and self.clear_take_profit:
            raise ValueError("protect intent cannot set and clear take_profit")
        if (
            self.managed_exit is not None
            and self.managed_exit.bracket is not None
            and self.clear_take_profit
        ):
            raise ValueError("managed bracket cannot set and clear protection")
        if (
            self.managed_exit is not None
            and self.managed_exit.bracket is not None
            and (self.stop_loss is not None or self.take_profit is not None)
        ):
            raise ValueError("native SL/TP cannot duplicate a managed bracket")
        return self

    @property
    def action(self) -> TradeAction | None:
        if self.stop_loss is not None or self.take_profit is not None or self.clear_take_profit:
            return TradeAction.SLTP
        return None


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


_ORDER_INTENT_MODEL_TYPES = frozenset(
    {
        PlaceOrderIntent,
        PlaceOcoIntent,
        ModifyOcoIntent,
        CancelOcoIntent,
        ModifyManagedExitIntent,
        ClearManagedExitIntent,
        ModifyOrderIntent,
        CancelOrderIntent,
        ProtectPositionIntent,
        ClosePositionIntent,
        CloseByIntent,
    }
)


def _plain_order_intent_input(value: object) -> object:
    if type(value) in _ORDER_INTENT_MODEL_TYPES:
        try:
            storage: object = object.__getattribute__(value, "__dict__")
        except Exception:
            return {}
        if type(storage) is not dict:
            return {}
        candidate = cast(dict[object, object], storage).copy()
    elif type(value) is dict:
        candidate = cast(dict[object, object], value)
    else:
        return {}
    if not has_plain_bounded_validation_containers(candidate):
        return {}
    return candidate


type OrderIntent = Annotated[
    PlaceOrderIntent
    | PlaceOcoIntent
    | ModifyOcoIntent
    | CancelOcoIntent
    | ModifyManagedExitIntent
    | ClearManagedExitIntent
    | ModifyOrderIntent
    | CancelOrderIntent
    | ProtectPositionIntent
    | ClosePositionIntent
    | CloseByIntent,
    Field(discriminator="kind"),
    BeforeValidator(_plain_order_intent_input),
]

_ORDER_INTENT_ADAPTER: TypeAdapter[OrderIntent] = TypeAdapter(
    OrderIntent,
    config=ConfigDict(hide_input_in_errors=True),
)


def validate_order_intent(
    value: object,
    *,
    spec: StrategySpec | None = None,
    context: StrategyContext | None = None,
) -> OrderIntent:
    """Validate an intent structurally and, when supplied, against spec/context."""
    if not has_plain_bounded_validation_containers(value):
        return _ORDER_INTENT_ADAPTER.validate_python(None)
    intent = _ORDER_INTENT_ADAPTER.validate_python(value)
    if spec is None and context is None:
        return intent
    if spec is None or context is None:
        raise TypeError("spec and context must be supplied together")

    from trading_strategy_sdk.output import validate_strategy_output

    output = validate_strategy_output(
        {"signals": (), "intents": (intent,), "next_state": context.state},
        spec=spec,
        context=context,
    )
    return output.intents[0]
