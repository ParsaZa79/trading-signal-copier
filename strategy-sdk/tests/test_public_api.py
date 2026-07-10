from __future__ import annotations

import trading_strategy_sdk as sdk


def test_primary_contracts_are_available_from_package_root() -> None:
    expected = {
        "BarClosedEvent",
        "BarSubscription",
        "ClosedBar",
        "OrderIntent",
        "OrderType",
        "Position",
        "PositionMode",
        "SignalIntent",
        "StrategyContext",
        "StrategySpec",
        "StrategyState",
    }

    assert expected <= set(sdk.__all__)
    assert all(hasattr(sdk, name) for name in expected)
