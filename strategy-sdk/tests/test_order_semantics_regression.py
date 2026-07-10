from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

import trading_strategy_sdk as sdk


def _stop_limit(
    model_name: str,
    order_type: sdk.OrderType,
    *,
    trigger: str,
    limit: str,
    stop_loss: str,
    take_profit: str | None = None,
    filling: sdk.OrderFilling = sdk.OrderFilling.RETURN,
) -> object:
    values: dict[str, Any] = {
        "symbol": sdk.Symbol.EURUSD,
        "order_type": order_type,
        "entry_price": Decimal(trigger),
        "stop_limit_price": Decimal(limit),
        "stop_loss": Decimal(stop_loss),
        "take_profit": Decimal(take_profit) if take_profit is not None else None,
        "filling": filling,
    }
    if model_name == "PlaceOrderIntent":
        return sdk.PlaceOrderIntent(intent_id="stop_limit", **values)
    return sdk.OcoLeg(leg_id="stop_limit", **values)


@pytest.mark.parametrize("model_name", ["PlaceOrderIntent", "OcoLeg"])
@pytest.mark.parametrize(
    ("order_type", "trigger", "limit", "stop_loss", "take_profit"),
    [
        (sdk.OrderType.BUY_STOP_LIMIT, "1.1050", "1.1040", "1.1030", "1.1060"),
        (sdk.OrderType.SELL_STOP_LIMIT, "1.0950", "1.0960", "1.0970", "1.0940"),
    ],
)
def test_stop_limit_price_is_a_limit_beyond_the_trigger_in_the_correct_direction(
    model_name: str,
    order_type: sdk.OrderType,
    trigger: str,
    limit: str,
    stop_loss: str,
    take_profit: str,
) -> None:
    intent = _stop_limit(
        model_name,
        order_type,
        trigger=trigger,
        limit=limit,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )

    assert intent.stop_limit_price == Decimal(limit)


@pytest.mark.parametrize("model_name", ["PlaceOrderIntent", "OcoLeg"])
@pytest.mark.parametrize(
    ("order_type", "trigger", "invalid_limit", "stop_loss"),
    [
        (sdk.OrderType.BUY_STOP_LIMIT, "1.1050", "1.1050", "1.0950"),
        (sdk.OrderType.BUY_STOP_LIMIT, "1.1050", "1.1060", "1.0950"),
        (sdk.OrderType.SELL_STOP_LIMIT, "1.0950", "1.0950", "1.1050"),
        (sdk.OrderType.SELL_STOP_LIMIT, "1.0950", "1.0940", "1.1050"),
    ],
)
def test_stop_limit_rejects_equal_or_inverted_limit_price(
    model_name: str,
    order_type: sdk.OrderType,
    trigger: str,
    invalid_limit: str,
    stop_loss: str,
) -> None:
    with pytest.raises(ValidationError, match=r"stop.limit|limit.*trigger|trigger.*limit"):
        _stop_limit(
            model_name,
            order_type,
            trigger=trigger,
            limit=invalid_limit,
            stop_loss=stop_loss,
        )


@pytest.mark.parametrize("model_name", ["PlaceOrderIntent", "OcoLeg"])
@pytest.mark.parametrize(
    ("order_type", "trigger", "limit", "invalid_stop"),
    [
        (sdk.OrderType.BUY_STOP_LIMIT, "1.1050", "1.1040", "1.1045"),
        (sdk.OrderType.BUY_STOP_LIMIT, "1.1050", "1.1040", "1.1040"),
        (sdk.OrderType.SELL_STOP_LIMIT, "1.0950", "1.0960", "1.0955"),
        (sdk.OrderType.SELL_STOP_LIMIT, "1.0950", "1.0960", "1.0960"),
    ],
)
def test_stop_limit_protection_uses_eventual_limit_as_the_loss_basis(
    model_name: str,
    order_type: sdk.OrderType,
    trigger: str,
    limit: str,
    invalid_stop: str,
) -> None:
    with pytest.raises(ValidationError, match=r"stop loss|stop_loss|limit"):
        _stop_limit(
            model_name,
            order_type,
            trigger=trigger,
            limit=limit,
            stop_loss=invalid_stop,
        )


@pytest.mark.parametrize("model_name", ["PlaceOrderIntent", "OcoLeg"])
@pytest.mark.parametrize(
    ("order_type", "trigger", "limit", "stop_loss", "take_profit"),
    [
        (sdk.OrderType.BUY_STOP_LIMIT, "1.1050", "1.1040", "1.1030", "1.1045"),
        (sdk.OrderType.SELL_STOP_LIMIT, "1.0950", "1.0960", "1.0970", "1.0955"),
    ],
)
def test_stop_limit_allows_profit_between_limit_and_trigger(
    model_name: str,
    order_type: sdk.OrderType,
    trigger: str,
    limit: str,
    stop_loss: str,
    take_profit: str,
) -> None:
    intent = _stop_limit(
        model_name,
        order_type,
        trigger=trigger,
        limit=limit,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )

    assert intent.take_profit == Decimal(take_profit)


def _pending(model_name: str, order_type: sdk.OrderType, filling: sdk.OrderFilling) -> object:
    is_buy = order_type.is_buy
    values: dict[str, Any] = {
        "symbol": sdk.Symbol.EURUSD,
        "order_type": order_type,
        "entry_price": Decimal("1.1000"),
        "stop_loss": Decimal("1.0800" if is_buy else "1.1200"),
        "filling": filling,
    }
    if order_type is sdk.OrderType.BUY_STOP_LIMIT:
        values["stop_limit_price"] = Decimal("1.0900")
    elif order_type is sdk.OrderType.SELL_STOP_LIMIT:
        values["stop_limit_price"] = Decimal("1.1100")
    if model_name == "PlaceOrderIntent":
        return sdk.PlaceOrderIntent(intent_id="pending_fill", **values)
    return sdk.OcoLeg(leg_id="pending_fill", **values)


@pytest.mark.parametrize("model_name", ["PlaceOrderIntent", "OcoLeg"])
@pytest.mark.parametrize(
    "order_type",
    [
        sdk.OrderType.BUY_LIMIT,
        sdk.OrderType.SELL_LIMIT,
        sdk.OrderType.BUY_STOP,
        sdk.OrderType.SELL_STOP,
        sdk.OrderType.BUY_STOP_LIMIT,
        sdk.OrderType.SELL_STOP_LIMIT,
    ],
)
@pytest.mark.parametrize("filling", [sdk.OrderFilling.FOK, sdk.OrderFilling.IOC])
def test_every_pending_order_rejects_immediate_filling_policies(
    model_name: str,
    order_type: sdk.OrderType,
    filling: sdk.OrderFilling,
) -> None:
    with pytest.raises(ValidationError, match=r"pending|filling|RETURN"):
        _pending(model_name, order_type, filling)


@pytest.mark.parametrize("model_name", ["PlaceOrderIntent", "OcoLeg"])
@pytest.mark.parametrize(
    "order_type",
    [
        sdk.OrderType.BUY_LIMIT,
        sdk.OrderType.SELL_LIMIT,
        sdk.OrderType.BUY_STOP,
        sdk.OrderType.SELL_STOP,
        sdk.OrderType.BUY_STOP_LIMIT,
        sdk.OrderType.SELL_STOP_LIMIT,
    ],
)
def test_every_pending_order_accepts_return_filling(
    model_name: str, order_type: sdk.OrderType
) -> None:
    intent = _pending(model_name, order_type, sdk.OrderFilling.RETURN)

    assert intent.filling is sdk.OrderFilling.RETURN


@pytest.mark.parametrize("model_name", ["PlaceOrderIntent", "OcoLeg"])
@pytest.mark.parametrize(
    ("order_type", "allowed"),
    [
        (sdk.OrderType.BUY_LIMIT, True),
        (sdk.OrderType.SELL_LIMIT, True),
        (sdk.OrderType.BUY_STOP, False),
        (sdk.OrderType.SELL_STOP, False),
        (sdk.OrderType.BUY_STOP_LIMIT, True),
        (sdk.OrderType.SELL_STOP_LIMIT, True),
    ],
)
def test_book_or_cancel_is_only_valid_for_passive_pending_types(
    model_name: str, order_type: sdk.OrderType, allowed: bool
) -> None:
    if allowed:
        intent = _pending(model_name, order_type, sdk.OrderFilling.BOC)
        assert intent.filling is sdk.OrderFilling.BOC
    else:
        with pytest.raises(ValidationError, match="BOC"):
            _pending(model_name, order_type, sdk.OrderFilling.BOC)


@pytest.mark.parametrize("intent_name", ["ModifyOrderIntent", "ProtectPositionIntent"])
def test_bounded_loss_stop_cannot_be_cleared(intent_name: str) -> None:
    values = {"intent_id": "clear_stop", "clear_stop_loss": True}
    if intent_name == "ModifyOrderIntent":
        values["order_id"] = "order_1"
    else:
        values["position_id"] = "position_1"

    with pytest.raises(ValidationError, match=r"bounded|stop loss|stop_loss"):
        getattr(sdk, intent_name)(**values)


@pytest.mark.parametrize("intent_name", ["ModifyOrderIntent", "ProtectPositionIntent"])
def test_bounded_loss_clear_stop_is_not_advertised_by_the_schema(intent_name: str) -> None:
    assert "clear_stop_loss" not in getattr(sdk, intent_name).model_fields


@pytest.mark.parametrize("intent_name", ["ModifyOrderIntent", "ProtectPositionIntent"])
def test_bounded_loss_does_not_prevent_clearing_take_profit(intent_name: str) -> None:
    values = {"intent_id": "clear_profit", "clear_take_profit": True}
    if intent_name == "ModifyOrderIntent":
        values["order_id"] = "order_1"
    else:
        values["position_id"] = "position_1"

    intent = getattr(sdk, intent_name)(**values)

    assert intent.clear_take_profit


def _native_managed_conflict(intent_name: str, native_field: str) -> object:
    bracket = sdk.BracketExit(stop_loss=Decimal("1.0900"), take_profit=Decimal("1.1200"))
    managed = sdk.ManagedExitPlan(bracket=bracket)
    native_value = Decimal("1.0900" if native_field == "stop_loss" else "1.1200")
    if intent_name == "PlaceOrderIntent":
        return sdk.PlaceOrderIntent(
            intent_id="conflict",
            symbol=sdk.Symbol.EURUSD,
            order_type=sdk.OrderType.BUY_LIMIT,
            entry_price=Decimal("1.1000"),
            managed_exit=managed,
            **{native_field: native_value},
        )
    if intent_name == "OcoLeg":
        return sdk.OcoLeg(
            leg_id="conflict",
            symbol=sdk.Symbol.EURUSD,
            order_type=sdk.OrderType.BUY_LIMIT,
            entry_price=Decimal("1.1000"),
            bracket=bracket,
            **{native_field: native_value},
        )
    return sdk.ProtectPositionIntent(
        intent_id="conflict",
        position_id="position_1",
        managed_exit=managed,
        **{native_field: native_value},
    )


@pytest.mark.parametrize("intent_name", ["PlaceOrderIntent", "OcoLeg", "ProtectPositionIntent"])
@pytest.mark.parametrize("native_field", ["stop_loss", "take_profit"])
def test_native_and_managed_bracket_protection_cannot_conflict(
    intent_name: str, native_field: str
) -> None:
    with pytest.raises(ValidationError, match=r"native|managed|bracket|duplicate"):
        _native_managed_conflict(intent_name, native_field)


def _oco_group() -> sdk.OcoGroup:
    return sdk.OcoGroup(
        group_id="breakout",
        legs=(
            sdk.OcoLeg(
                leg_id="long",
                symbol=sdk.Symbol.EURUSD,
                order_type=sdk.OrderType.BUY_STOP,
                entry_price=Decimal("1.1050"),
                stop_loss=Decimal("1.0950"),
            ),
            sdk.OcoLeg(
                leg_id="short",
                symbol=sdk.Symbol.EURUSD,
                order_type=sdk.OrderType.SELL_STOP,
                entry_price=Decimal("1.0950"),
                stop_loss=Decimal("1.1050"),
            ),
        ),
    )


def test_platform_oco_has_no_single_native_trade_action() -> None:
    intent = sdk.PlaceOcoIntent(intent_id="oco", group=_oco_group())

    assert intent.action is None


def test_managed_only_position_protection_has_no_native_sltp_action() -> None:
    intent = sdk.ProtectPositionIntent(
        intent_id="trail",
        position_id="position_1",
        managed_exit=sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(distance=Decimal("0.0050"))
        ),
    )

    assert intent.action is None


@pytest.mark.parametrize("native_change", ["stop_loss", "clear_take_profit"])
def test_mixed_native_and_managed_protection_reports_its_native_action(
    native_change: str,
) -> None:
    values: dict[str, object] = {
        "intent_id": "mixed_protection",
        "position_id": "position_1",
        "managed_exit": sdk.ManagedExitPlan(
            trailing_stop=sdk.TrailingStop(distance=Decimal("0.0050"))
        ),
    }
    values[native_change] = Decimal("1.0900") if native_change == "stop_loss" else True

    assert sdk.ProtectPositionIntent(**values).action is sdk.TradeAction.SLTP


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        (
            sdk.PlaceOrderIntent(
                intent_id="market",
                symbol=sdk.Symbol.EURUSD,
                order_type=sdk.OrderType.BUY,
                stop_loss=Decimal("1.0900"),
            ),
            sdk.TradeAction.DEAL,
        ),
        (
            sdk.PlaceOrderIntent(
                intent_id="pending",
                symbol=sdk.Symbol.EURUSD,
                order_type=sdk.OrderType.BUY_LIMIT,
                entry_price=Decimal("1.1000"),
                stop_loss=Decimal("1.0900"),
            ),
            sdk.TradeAction.PENDING,
        ),
        (
            sdk.ModifyOrderIntent(
                intent_id="modify", order_id="order_1", entry_price=Decimal("1.1000")
            ),
            sdk.TradeAction.MODIFY,
        ),
        (sdk.CancelOrderIntent(intent_id="cancel", order_id="order_1"), sdk.TradeAction.REMOVE),
        (
            sdk.ProtectPositionIntent(
                intent_id="protect", position_id="position_1", stop_loss=Decimal("1.0900")
            ),
            sdk.TradeAction.SLTP,
        ),
        (
            sdk.ClosePositionIntent(intent_id="close", position_id="position_1"),
            sdk.TradeAction.DEAL,
        ),
        (
            sdk.CloseByIntent(
                intent_id="close_by",
                position_id="position_1",
                opposite_position_id="position_2",
            ),
            sdk.TradeAction.CLOSE_BY,
        ),
    ],
)
def test_true_native_intents_retain_exact_mt5_action(
    intent: object, expected: sdk.TradeAction
) -> None:
    assert intent.action is expected
