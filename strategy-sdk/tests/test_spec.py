from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from trading_strategy_sdk.orders import OrderFilling, OrderType
from trading_strategy_sdk.positions import PositionMode
from trading_strategy_sdk.spec import (
    BarSubscription,
    BoundedLossSpec,
    Capability,
    DependencySpec,
    ParameterSpec,
    ParameterType,
    RuleSpec,
    StrategySpec,
    Symbol,
    SynchronizationMode,
    SynchronizationSpec,
    Timeframe,
    TriggerSpec,
    WarmupRequirement,
)


def _subscription(symbol: Symbol, timeframe: Timeframe) -> BarSubscription:
    return BarSubscription(symbol=symbol, timeframe=timeframe)


def _valid_spec(**updates: object) -> StrategySpec:
    eurusd_m5 = _subscription(Symbol.EURUSD, Timeframe.M5)
    xauusd_h1 = _subscription(Symbol.XAUUSD, Timeframe.H1)
    values: dict[str, object] = {
        "subscriptions": (eurusd_m5, xauusd_h1),
        "warmup": (
            WarmupRequirement(subscription=eurusd_m5, bars=200),
            WarmupRequirement(subscription=xauusd_h1, bars=50),
        ),
        "triggers": (
            TriggerSpec(name="fast_close", subscriptions=(eurusd_m5,)),
            TriggerSpec(name="slow_close", subscriptions=(xauusd_h1,)),
        ),
        "synchronization": SynchronizationSpec(
            mode=SynchronizationMode.LATEST_CLOSED,
            required_subscriptions=(eurusd_m5, xauusd_h1),
        ),
        "entries": (RuleSpec(name="trend_entry", description="Enter on confirmed trend."),),
        "exits": (RuleSpec(name="protective_exit", description="Exit at the technical stop."),),
        "parameters": (
            ParameterSpec(
                name="lookback_bars",
                kind=ParameterType.INTEGER,
                default=20,
                minimum=5,
                maximum=100,
            ),
        ),
        "position_mode": PositionMode.HEDGING,
        "required_capabilities": frozenset(
            {
                Capability.MULTI_SYMBOL_DATA,
                Capability.MULTI_TIMEFRAME_DATA,
                Capability.RETURN_FILLING,
            }
        ),
        "order_types": frozenset({OrderType.BUY, OrderType.SELL_STOP_LIMIT}),
        "filling_policies": frozenset({OrderFilling.RETURN}),
        "dependencies": (
            DependencySpec(
                name="numpy",
                version="2.2.1",
                hashes=(f"sha256:{'a' * 64}",),
            ),
        ),
        "disclosures": ("Signals can be inactive during market gaps.",),
        "bounded_loss": BoundedLossSpec(
            stop_loss_required=True,
            gap_risk_disclosed=True,
            description="Every entry supplies a technical invalidation price.",
        ),
    }
    values.update(updates)
    return StrategySpec.model_validate(values)


def test_valid_multisymbol_multitimeframe_spec_round_trips() -> None:
    spec = _valid_spec()

    assert spec.symbols == (Symbol.EURUSD, Symbol.XAUUSD)
    assert spec.timeframes == (Timeframe.M5, Timeframe.H1)
    assert StrategySpec.model_validate_json(spec.model_dump_json()) == spec

    with pytest.raises(ValidationError, match="frozen"):
        spec.position_mode = PositionMode.NETTING  # type: ignore[misc]


def test_r1_universe_and_minimum_timeframe_are_validated() -> None:
    with pytest.raises(ValidationError):
        BarSubscription.model_validate({"symbol": "BTCUSD", "timeframe": "M5"})

    with pytest.raises(ValidationError):
        BarSubscription.model_validate({"symbol": "EURUSD", "timeframe": "M1"})


@pytest.mark.parametrize(
    "update_factory",
    [
        lambda: {
            "subscriptions": (
                _subscription(Symbol.EURUSD, Timeframe.M5),
                _subscription(Symbol.EURUSD, Timeframe.M5),
            )
        },
        lambda: {
            "warmup": (
                WarmupRequirement(subscription=_subscription(Symbol.EURUSD, Timeframe.M5), bars=20),
            )
        },
        lambda: {
            "triggers": (
                TriggerSpec(
                    name="unknown_feed",
                    subscriptions=(_subscription(Symbol.GBPUSD, Timeframe.M15),),
                ),
            )
        },
        lambda: {
            "synchronization": SynchronizationSpec(
                mode=SynchronizationMode.EXACT_CLOSE,
                required_subscriptions=(_subscription(Symbol.EURUSD, Timeframe.M5),),
            )
        },
    ],
)
def test_subscription_references_must_be_complete_and_declared(
    update_factory: Callable[[], dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        _valid_spec(**update_factory())


def test_multi_feed_and_filling_capabilities_are_explicit() -> None:
    with pytest.raises(ValidationError, match="MULTI_SYMBOL_DATA"):
        _valid_spec(
            required_capabilities=frozenset(
                {Capability.MULTI_TIMEFRAME_DATA, Capability.RETURN_FILLING}
            )
        )

    with pytest.raises(ValidationError, match="DEPTH_OF_MARKET"):
        _valid_spec(
            filling_policies=frozenset({OrderFilling.FOK}),
            required_capabilities=frozenset(
                {
                    Capability.MULTI_SYMBOL_DATA,
                    Capability.MULTI_TIMEFRAME_DATA,
                    Capability.FOK_FILLING,
                }
            ),
        )


@pytest.mark.parametrize(
    ("dependency", "error"),
    [
        (
            DependencySpec.model_construct(
                name="numpy", version=">=2", hashes=(f"sha256:{'a' * 64}",)
            ),
            "exact",
        ),
        (
            DependencySpec.model_construct(name="numpy", version="2.2.1", hashes=("sha256:nope",)),
            "SHA-256",
        ),
    ],
)
def test_dependencies_require_exact_versions_and_hashes(
    dependency: DependencySpec, error: str
) -> None:
    with pytest.raises(ValidationError, match=error):
        DependencySpec.model_validate(dependency.model_dump())


@pytest.mark.parametrize("version", ["1..2", "1.0!", "1!!!", "1.0+"])
def test_dependencies_reject_invalid_pep440_versions(version: str) -> None:
    with pytest.raises(ValidationError, match="exact PEP 440"):
        DependencySpec(name="example", version=version, hashes=(f"sha256:{'a' * 64}",))


def test_dependency_versions_and_names_are_canonicalized() -> None:
    dependency = DependencySpec(
        name="Example__Package.Name",
        version="1!2.0RC1.post2.dev3+CPU",
        hashes=(f"sha256:{'A' * 64}",),
    )

    assert dependency.name == "example-package-name"
    assert dependency.version == "1!2.0rc1.post2.dev3+cpu"
    assert dependency.hashes == (f"sha256:{'a' * 64}",)


def test_bounded_loss_and_parameter_risk_separation_are_mandatory() -> None:
    with pytest.raises(ValidationError, match="stop loss"):
        _valid_spec(
            bounded_loss=BoundedLossSpec.model_construct(
                stop_loss_required=False,
                gap_risk_disclosed=True,
                description="No stop.",
            )
        )

    with pytest.raises(ValidationError, match="risk policy"):
        ParameterSpec(name="lot_size", kind=ParameterType.NUMBER, default=0.1)


def test_unknown_spec_fields_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        StrategySpec.model_validate({**_valid_spec().model_dump(), "account_balance": 500})


def test_unordered_spec_fields_serialize_canonically() -> None:
    payload = json.loads(_valid_spec().model_dump_json())

    assert payload["required_capabilities"] == [
        "multi_symbol_data",
        "multi_timeframe_data",
        "return_filling",
    ]
    assert payload["order_types"] == [0, 7]
    assert payload["filling_policies"] == [2]


def test_close_by_requires_hedging_mode() -> None:
    with pytest.raises(ValidationError, match=r"CLOSE_BY.*HEDGING"):
        _valid_spec(
            position_mode=PositionMode.NETTING,
            order_types=frozenset({OrderType.BUY, OrderType.CLOSE_BY}),
        )


@pytest.mark.parametrize(
    "name",
    [
        "risk_pct",
        "risk_per_trade",
        "lotsize",
        "position_size",
        "accountbalance",
        "max_open_risk",
    ],
)
def test_strategy_parameters_cannot_disguise_sizing_or_user_risk(name: str) -> None:
    with pytest.raises(ValidationError, match="risk policy"):
        ParameterSpec(name=name, kind=ParameterType.NUMBER, default=1)


def test_zero_bar_warmup_is_an_explicit_valid_choice() -> None:
    subscription = _subscription(Symbol.EURUSD, Timeframe.M5)
    assert WarmupRequirement(subscription=subscription, bars=0).bars == 0
