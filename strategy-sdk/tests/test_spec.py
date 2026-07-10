from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trading_strategy_sdk.orders import BreakEven, OrderFilling, OrderType
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


def test_strategy_spec_exposes_canonical_bytes_and_prefixed_sha256_identity() -> None:
    spec = _valid_spec()

    canonical = spec.canonical_bytes()
    digest = spec.sha256_digest()

    assert canonical == canonical.strip()
    assert canonical == spec.canonical_bytes()
    assert digest == f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    assert digest == spec.sha256_digest()


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (Decimal("1"), Decimal("1.0000")),
        (Decimal("123.4500"), Decimal("123.45")),
        (Decimal("0"), Decimal("-0.000")),
    ],
)
def test_canonical_identity_normalizes_numeric_decimal_equivalents(
    left: Decimal, right: Decimal
) -> None:
    first = BreakEven(trigger_price=Decimal("2"), offset=left)
    second = BreakEven(trigger_price=Decimal("2.000"), offset=right)

    assert first.canonical_bytes() == second.canonical_bytes()
    assert first.sha256_digest() == second.sha256_digest()


def test_canonical_identity_revalidates_constructed_artifacts() -> None:
    valid = _valid_spec()
    invalid = StrategySpec.model_construct(
        **{
            **valid.model_dump(round_trip=True),
            "subscriptions": (valid.subscriptions[0], valid.subscriptions[0]),
        }
    )

    with pytest.raises(ValidationError, match="unique"):
        invalid.canonical_bytes()


def test_canonical_identity_normalizes_unordered_spec_fields_but_preserves_rule_order() -> None:
    original = _valid_spec()
    reordered_unordered = _valid_spec(
        subscriptions=tuple(reversed(original.subscriptions)),
        warmup=tuple(reversed(original.warmup)),
        triggers=tuple(reversed(original.triggers)),
        parameters=tuple(reversed(original.parameters)),
        dependencies=tuple(reversed(original.dependencies)),
    )
    reversed_entries = _valid_spec(
        entries=(
            RuleSpec(name="second", description="Second order-sensitive rule."),
            RuleSpec(name="first", description="First order-sensitive rule."),
        )
    )
    forward_entries = _valid_spec(entries=tuple(reversed(reversed_entries.entries)))

    assert reordered_unordered.canonical_bytes() == original.canonical_bytes()
    assert reordered_unordered.sha256_digest() == original.sha256_digest()
    assert reversed_entries.canonical_bytes() != forward_entries.canonical_bytes()


def test_other_immutable_contracts_share_the_documented_artifact_identity_api() -> None:
    hashes = (f"sha256:{'a' * 64}", f"sha256:{'b' * 64}")
    dependency = DependencySpec(name="numpy", version="2.2.1", hashes=hashes)
    reordered = DependencySpec(name="numpy", version="2.2.1", hashes=tuple(reversed(hashes)))

    assert dependency.canonical_bytes().startswith(b'{"hashes":')
    assert dependency.sha256_digest().startswith("sha256:")
    assert dependency.canonical_bytes() == reordered.canonical_bytes()
    assert dependency.sha256_digest() == reordered.sha256_digest()


def test_canonical_identity_normalizes_unordered_oco_legs_and_position_provenance() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal

    import trading_strategy_sdk as sdk

    legs = (
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
    )
    first_group = sdk.OcoGroup(group_id="breakout", legs=legs)
    second_group = sdk.OcoGroup(group_id="breakout", legs=tuple(reversed(legs)))
    first_position = sdk.Position(
        position_id="position_1",
        symbol=sdk.Symbol.EURUSD,
        side=sdk.PositionSide.BUY,
        average_price=Decimal("1.1000"),
        opened_at=datetime(2026, 7, 10, tzinfo=UTC),
        source_order_ids=("order_2", "order_1"),
    )
    second_position = first_position.model_copy(update={"source_order_ids": ("order_1", "order_2")})

    assert first_group.sha256_digest() == second_group.sha256_digest()
    assert first_position.sha256_digest() == second_position.sha256_digest()


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
