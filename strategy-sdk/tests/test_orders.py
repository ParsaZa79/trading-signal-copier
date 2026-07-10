from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_strategy_sdk.orders import (
    BracketExit,
    BreakEven,
    ManagedExitPlan,
    OcoGroup,
    OcoLeg,
    OrderFilling,
    OrderTime,
    OrderType,
    PartialExit,
    TradeAction,
    TrailingStop,
)
from trading_strategy_sdk.spec import Symbol


def test_all_mt5_order_action_expiration_and_filling_values_are_exact() -> None:
    assert {member.name: member.value for member in OrderType} == {
        "BUY": 0,
        "SELL": 1,
        "BUY_LIMIT": 2,
        "SELL_LIMIT": 3,
        "BUY_STOP": 4,
        "SELL_STOP": 5,
        "BUY_STOP_LIMIT": 6,
        "SELL_STOP_LIMIT": 7,
        "CLOSE_BY": 8,
    }
    assert {member.name: member.value for member in TradeAction} == {
        "DEAL": 1,
        "PENDING": 5,
        "SLTP": 6,
        "MODIFY": 7,
        "REMOVE": 8,
        "CLOSE_BY": 10,
    }
    assert {member.name: member.value for member in OrderTime} == {
        "GTC": 0,
        "DAY": 1,
        "SPECIFIED": 2,
        "SPECIFIED_DAY": 3,
    }
    assert {member.name: member.value for member in OrderFilling} == {
        "FOK": 0,
        "IOC": 1,
        "RETURN": 2,
        "BOC": 3,
    }


def test_stop_limit_and_expiration_fields_are_validated() -> None:
    expires_at = datetime(2026, 7, 11, tzinfo=UTC)
    leg = OcoLeg(
        leg_id="breakout_long",
        symbol=Symbol.EURUSD,
        order_type=OrderType.BUY_STOP_LIMIT,
        entry_price=Decimal("1.1050"),
        stop_limit_price=Decimal("1.1052"),
        stop_loss=Decimal("1.0950"),
        filling=OrderFilling.RETURN,
        time=OrderTime.SPECIFIED,
        expires_at=expires_at,
    )

    assert leg.stop_limit_price == Decimal("1.1052")
    assert OcoLeg.model_validate_json(leg.model_dump_json()) == leg

    with pytest.raises(ValidationError, match="stop_limit_price"):
        OcoLeg(
            leg_id="missing_limit",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY_STOP_LIMIT,
            entry_price=Decimal("1.1050"),
            stop_loss=Decimal("1.0950"),
        )

    with pytest.raises(ValidationError, match="expires_at"):
        OcoLeg(
            leg_id="missing_expiry",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY_LIMIT,
            entry_price=Decimal("1.0950"),
            stop_loss=Decimal("1.0900"),
            time=OrderTime.SPECIFIED_DAY,
        )


def test_oco_legs_are_pending_and_boc_is_limited_to_passive_order_types() -> None:
    with pytest.raises(ValidationError, match="pending"):
        OcoLeg(
            leg_id="market",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY,
            entry_price=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
        )

    with pytest.raises(ValidationError, match="BOC"):
        OcoLeg(
            leg_id="active_stop",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY_STOP,
            entry_price=Decimal("1.1050"),
            stop_loss=Decimal("1.0950"),
            filling=OrderFilling.BOC,
        )


def test_platform_managed_oco_requires_distinct_legs() -> None:
    buy = OcoLeg(
        leg_id="buy_breakout",
        symbol=Symbol.EURUSD,
        order_type=OrderType.BUY_STOP,
        entry_price=Decimal("1.1050"),
        stop_loss=Decimal("1.0950"),
    )
    sell = OcoLeg(
        leg_id="sell_breakout",
        symbol=Symbol.EURUSD,
        order_type=OrderType.SELL_STOP,
        entry_price=Decimal("1.0950"),
        stop_loss=Decimal("1.1050"),
    )

    group = OcoGroup(group_id="london_breakout", legs=(buy, sell))
    assert group.legs == (buy, sell)

    with pytest.raises(ValidationError):
        OcoGroup(group_id="too_small", legs=(buy,))

    with pytest.raises(ValidationError, match="leg_id"):
        OcoGroup(group_id="duplicate", legs=(buy, buy))


def test_brackets_trailing_break_even_and_partials_form_one_managed_plan() -> None:
    plan = ManagedExitPlan(
        bracket=BracketExit(stop_loss=Decimal("1.0950"), take_profit=Decimal("1.1200")),
        trailing_stop=TrailingStop(
            distance=Decimal("0.0020"),
            activation_price=Decimal("1.1100"),
            step=Decimal("0.0005"),
        ),
        break_even=BreakEven(trigger_price=Decimal("1.1080"), offset=Decimal("0.0001")),
        partials=(
            PartialExit(trigger_price=Decimal("1.1100"), fraction=Decimal("0.5")),
            PartialExit(trigger_price=Decimal("1.1150"), fraction=Decimal("0.5")),
        ),
    )

    assert sum((item.fraction for item in plan.partials), start=Decimal(0)) == Decimal(1)

    with pytest.raises(ValidationError, match="cumulative"):
        ManagedExitPlan(
            partials=(
                PartialExit(trigger_price=Decimal("1.1100"), fraction=Decimal("0.6")),
                PartialExit(trigger_price=Decimal("1.1150"), fraction=Decimal("0.5")),
            )
        )

    with pytest.raises(ValidationError, match="at least one"):
        ManagedExitPlan()


def test_oco_entries_require_bounded_and_directionally_valid_protection() -> None:
    with pytest.raises(ValidationError, match="stop loss"):
        OcoLeg(
            leg_id="unbounded",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY_STOP,
            entry_price=Decimal("1.1050"),
        )

    with pytest.raises(ValidationError, match="below"):
        OcoLeg(
            leg_id="inverted",
            symbol=Symbol.EURUSD,
            order_type=OrderType.BUY_STOP,
            entry_price=Decimal("1.1050"),
            stop_loss=Decimal("1.1100"),
        )
