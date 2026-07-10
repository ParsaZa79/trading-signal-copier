from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_strategy_sdk.intents import (
    CancelOcoIntent,
    CancelOrderIntent,
    ClearManagedExitIntent,
    CloseByIntent,
    ClosePositionIntent,
    ModifyManagedExitIntent,
    ModifyOcoIntent,
    ModifyOrderIntent,
    PlaceOcoIntent,
    PlaceOrderIntent,
    ProtectPositionIntent,
    SignalIntent,
    validate_order_intent,
)
from trading_strategy_sdk.orders import (
    OcoGroup,
    OcoLeg,
    OrderFilling,
    OrderTime,
    OrderType,
    TradeAction,
)
from trading_strategy_sdk.positions import PositionSide
from trading_strategy_sdk.spec import Symbol

INTENT_MODELS = (
    SignalIntent,
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
)
FORBIDDEN_FIELDS = {
    "account",
    "account_balance",
    "allocation",
    "balance",
    "credential",
    "credentials",
    "equity",
    "final_lot",
    "leverage",
    "login",
    "lot",
    "lot_size",
    "password",
    "payload",
    "policy",
    "risk",
    "risk_policy",
    "secret",
    "user_policy",
    "volume",
}


def _place_order(**updates: object) -> PlaceOrderIntent:
    values: dict[str, object] = {
        "intent_id": "entry_1",
        "symbol": Symbol.EURUSD,
        "order_type": OrderType.BUY_LIMIT,
        "entry_price": Decimal("1.0950"),
        "stop_loss": Decimal("1.0900"),
        "take_profit": Decimal("1.1100"),
        "filling": OrderFilling.RETURN,
    }
    values.update(updates)
    return PlaceOrderIntent.model_validate(values)


def test_intent_schemas_structurally_exclude_execution_and_user_risk_fields() -> None:
    for model in INTENT_MODELS:
        field_names = set(model.model_fields)
        assert field_names.isdisjoint(FORBIDDEN_FIELDS), model.__name__


@pytest.mark.parametrize(
    "forbidden",
    [
        "volume",
        "lot_size",
        "final_lot",
        "account_balance",
        "credentials",
        "risk_policy",
        "leverage",
        "allocation",
    ],
)
def test_place_order_cannot_accept_forbidden_fields(forbidden: str) -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        _place_order(**{forbidden: object()})


def test_signal_intent_carries_only_direction_and_technical_prices() -> None:
    signal = SignalIntent(
        signal_id="trend_entry_1",
        rule_name="trend_entry",
        symbol=Symbol.EURUSD,
        side=PositionSide.BUY,
        reference_price=Decimal("1.1000"),
        stop_loss=Decimal("1.0950"),
        take_profit=Decimal("1.1100"),
    )

    assert set(signal.model_dump()) == {
        "kind",
        "signal_id",
        "rule_name",
        "symbol",
        "side",
        "reference_price",
        "stop_loss",
        "take_profit",
    }
    with pytest.raises(ValidationError, match="Extra inputs"):
        SignalIntent.model_validate({**signal.model_dump(), "account_balance": 500})


def test_discriminated_order_intent_decoder_rejects_hidden_volume() -> None:
    payload = _place_order().model_dump(mode="json")
    payload["volume"] = "0.10"

    with pytest.raises(ValidationError, match="Extra inputs"):
        validate_order_intent(payload)


def test_direct_intent_decoder_hides_untrusted_input_values() -> None:
    secret = "DO-NOT-ECHO-THIS-CREDENTIAL"
    with pytest.raises(ValidationError) as error:
        validate_order_intent({"kind": "unknown", "payload": secret})
    assert secret not in str(error.value)


def test_intent_copy_api_cannot_inject_an_unvalidated_field() -> None:
    intent = _place_order()

    with pytest.raises(ValidationError, match="Extra inputs"):
        intent.model_copy(update={"volume": Decimal("0.10")})


def test_market_and_pending_place_intents_validate_technical_prices() -> None:
    market = PlaceOrderIntent(
        intent_id="market_1",
        symbol=Symbol.EURUSD,
        order_type=OrderType.BUY,
        stop_loss=Decimal("1.0950"),
    )

    assert market.action is TradeAction.DEAL
    assert _place_order().action is TradeAction.PENDING

    with pytest.raises(ValidationError, match="entry_price"):
        PlaceOrderIntent(
            intent_id="invalid_market",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY,
            entry_price=Decimal("1.1000"),
        )

    with pytest.raises(ValidationError, match="entry_price"):
        PlaceOrderIntent(
            intent_id="invalid_pending",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY_STOP,
        )

    with pytest.raises(ValidationError, match="stop loss"):
        PlaceOrderIntent(
            intent_id="unbounded",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY_STOP,
            entry_price=Decimal("1.1050"),
        )


def test_modify_cancel_protect_close_and_close_by_are_explicit_actions() -> None:
    modify = ModifyOrderIntent(
        intent_id="modify_1", order_id="order_1", entry_price=Decimal("1.0960")
    )
    cancel = CancelOrderIntent(intent_id="cancel_1", order_id="order_1")
    protect = ProtectPositionIntent(
        intent_id="protect_1", position_id="position_1", stop_loss=Decimal("1.1000")
    )
    partial = ClosePositionIntent(
        intent_id="partial_1", position_id="position_1", fraction=Decimal("0.5")
    )
    close_by = CloseByIntent(
        intent_id="close_by_1", position_id="position_1", opposite_position_id="position_2"
    )

    assert modify.action is TradeAction.MODIFY
    assert cancel.action is TradeAction.REMOVE
    assert protect.action is TradeAction.SLTP
    assert partial.action is TradeAction.DEAL
    assert partial.fraction == Decimal("0.5")
    assert close_by.action is TradeAction.CLOSE_BY

    with pytest.raises(ValidationError, match="at least one"):
        ModifyOrderIntent(intent_id="empty_modify", order_id="order_1")
    with pytest.raises(ValidationError, match="at least one"):
        ProtectPositionIntent(intent_id="empty_protect", position_id="position_1")
    with pytest.raises(ValidationError, match="different"):
        CloseByIntent(
            intent_id="same_position",
            position_id="position_1",
            opposite_position_id="position_1",
        )


def test_modify_and_protect_intents_can_explicitly_clear_fields() -> None:
    modify = ModifyOrderIntent(
        intent_id="clear_expiration",
        order_id="order_1",
        time=OrderTime.GTC,
        clear_expiration=True,
        clear_take_profit=True,
    )
    protect = ProtectPositionIntent(
        intent_id="clear_take_profit",
        position_id="position_1",
        clear_take_profit=True,
    )

    assert modify.action is TradeAction.MODIFY
    assert modify.time is OrderTime.GTC
    assert protect.action is TradeAction.SLTP

    with pytest.raises(ValidationError, match=r"bounded|stop loss|stop_loss"):
        ProtectPositionIntent(
            intent_id="conflict",
            position_id="position_1",
            stop_loss=Decimal("1.1000"),
            clear_stop_loss=True,
        )


def test_oco_intent_carries_technical_legs_but_no_size() -> None:
    group = OcoGroup(
        group_id="breakout",
        legs=(
            OcoLeg(
                leg_id="long",
                symbol=Symbol.EURUSD,
                order_type=OrderType.BUY_STOP,
                entry_price=Decimal("1.1050"),
                stop_loss=Decimal("1.0950"),
            ),
            OcoLeg(
                leg_id="short",
                symbol=Symbol.EURUSD,
                order_type=OrderType.SELL_STOP,
                entry_price=Decimal("1.0950"),
                stop_loss=Decimal("1.1050"),
            ),
        ),
    )
    intent = PlaceOcoIntent(intent_id="oco_1", group=group)

    assert intent.action is None
    assert "volume" not in intent.model_dump_json()
