from __future__ import annotations

import json
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from itertools import permutations, product
from typing import cast

import pytest
from pydantic import TypeAdapter, ValidationError

from trading_strategy_sdk.context import BarSeries, StrategyContext
from trading_strategy_sdk.events import OHLC, BarClosedEvent, ClosedBar, ordered_events
from trading_strategy_sdk.market import BarSubscription, Symbol, Timeframe
from trading_strategy_sdk.orders import OrderFilling, OrderType
from trading_strategy_sdk.positions import PositionMode
from trading_strategy_sdk.spec import (
    BoundedLossSpec,
    Capability,
    DependencySpec,
    ParameterSpec,
    ParameterType,
    RuleSpec,
    StrategySpec,
    SynchronizationMode,
    SynchronizationSpec,
    TriggerSpec,
    WarmupRequirement,
)
from trading_strategy_sdk.state import JsonValue, StrategyState


def _ohlc(value: str) -> OHLC:
    price = Decimal(value)
    return OHLC(open=price, high=price, low=price, close=price)


def _bar(
    subscription: BarSubscription,
    close_time: datetime,
    value: str = "1.1000",
) -> ClosedBar:
    return ClosedBar(
        subscription=subscription,
        open_time=close_time - timedelta(minutes=subscription.timeframe.minutes),
        close_time=close_time,
        bid=_ohlc(value),
        ask=_ohlc(value),
    )


FORBIDDEN_PARAMETER_ALIASES = (
    "risk",
    "risk_limit",
    "capital_at_risk",
    "api_key",
    "access_token",
    "auth_token",
    "passphrase",
    "quantity",
    "qty",
    "units",
    "trade_size",
    "position_qty",
    "notional",
    "stake",
    "riskfactor",
    "riskcoefficient",
    "clientcredentials",
    "authtokenvalue",
    "tradestake",
    "tradequantity",
    "positionamount",
    "positionweight",
    "accountmargin",
    "ordercontracts",
    "bearersecret",
    "position_limit",
    "order_limit",
    "trade_limit",
    "max_orders",
    "max_open_orders",
)


@pytest.mark.parametrize("alias", FORBIDDEN_PARAMETER_ALIASES)
def test_parameter_aliases_cannot_smuggle_risk_credentials_or_sizing(alias: str) -> None:
    with pytest.raises(ValidationError):
        ParameterSpec(name=alias, kind=ParameterType.NUMBER, default=1)


@pytest.mark.parametrize(
    "alias",
    tuple(alias.replace("_", "") for alias in FORBIDDEN_PARAMETER_ALIASES if "_" in alias),
)
def test_separator_removal_cannot_bypass_sensitive_alias_rejection(alias: str) -> None:
    with pytest.raises(ValidationError):
        ParameterSpec(name=alias, kind=ParameterType.NUMBER, default=1)
    with pytest.raises(ValidationError):
        StrategyState.from_mapping({alias: 1})


@pytest.mark.parametrize(
    "state",
    [
        {"risk_limit": 2},
        {"settings": {"api_key": "credential-value"}},
        {"rules": [{"trade_size": 1}]},
        {"nested": [{"deeper": [{"access_token": "credential-value"}]}]},
        {"riskfactor": 1},
        {"settings": {"clientcredentials": "credential-value"}},
        {"r\u200bisk": 1},
        {"r\u0456sk": 1},
        {"ri\u0455k": 1},
        {"\u0455ecret": "credential-value"},
        {"pa\u0455\u0455word": "credential-value"},
        {"to\u043aen": "credential-value"},
        {"volu\u043ce": 1},
        {"\u03c3izing": 1},
    ],
)
def test_state_recursively_rejects_sensitive_keys(state: dict[str, JsonValue]) -> None:
    with pytest.raises(ValidationError):
        StrategyState.from_mapping(state)


def test_sensitive_validation_errors_hide_the_original_input() -> None:
    secret = "DO-NOT-ECHO-THIS-CREDENTIAL"

    with pytest.raises(ValidationError) as parameter_error:
        ParameterSpec(name="api_key", kind=ParameterType.STRING, default=secret)
    assert secret not in str(parameter_error.value)

    with pytest.raises(ValidationError) as state_error:
        StrategyState.from_mapping({"nested": {"access_token": secret}})
    assert secret not in str(state_error.value)


@pytest.mark.parametrize(
    "state_factory",
    [
        pytest.param(
            lambda: StrategyState.from_mapping(
                {"blob": "é" * (512 * 1024), "tail": "bounded-by-utf8-bytes"}
            ),
            id="mapping-bytes",
        ),
        pytest.param(
            lambda: StrategyState.from_json(
                json.dumps({"blob": "💣" * (256 * 1024)}, ensure_ascii=False)
            ),
            id="json-bytes",
        ),
        pytest.param(
            lambda: StrategyState.from_mapping(
                {"items": cast(list[JsonValue], list(range(20_000)))}
            ),
            id="cumulative-items",
        ),
        pytest.param(
            lambda: StrategyState.from_mapping(
                cast(dict[str, JsonValue], {"nested": _nested_mapping(100)})
            ),
            id="depth",
        ),
    ],
)
def test_state_has_bounded_bytes_depth_and_cumulative_items(state_factory: object) -> None:
    factory = cast(Callable[[], StrategyState], state_factory)
    with pytest.raises(ValidationError):
        factory()


def _nested_mapping(depth: int) -> dict[str, object]:
    value: dict[str, object] = {"leaf": True}
    for _ in range(depth):
        value = {"child": value}
    return value


@pytest.mark.parametrize(
    "state_factory",
    [
        pytest.param(lambda: StrategyState.from_mapping({"bad": object()}), id="python-object"),
        pytest.param(
            lambda: StrategyState.from_mapping(cast(dict[str, JsonValue], {1: "bad-key"})),
            id="non-string-key",
        ),
        pytest.param(lambda: StrategyState.from_mapping({"bad": float("nan")}), id="nan"),
        pytest.param(lambda: StrategyState.from_json("{"), id="malformed-json"),
        pytest.param(lambda: StrategyState.from_json("[]"), id="non-object-root"),
        pytest.param(lambda: StrategyState.from_json('{"same":1,"same":2}'), id="duplicate-key"),
    ],
)
def test_every_state_factory_validation_failure_is_a_pydantic_error(
    state_factory: object,
) -> None:
    factory = cast(Callable[[], StrategyState], state_factory)
    with pytest.raises(ValidationError):
        factory()


def test_state_update_validation_failures_are_pydantic_errors() -> None:
    with pytest.raises(ValidationError):
        StrategyState.empty().with_value("", True)
    with pytest.raises(ValidationError):
        StrategyState.empty().with_value("safe", cast(JsonValue, object()))
    with pytest.raises(ValidationError):
        StrategyState.empty().with_value(cast(str, []), True)


def test_parameter_numeric_overflow_is_a_pydantic_validation_error() -> None:
    with pytest.raises(ValidationError):
        ParameterSpec(
            name="lookback_bars",
            kind=ParameterType.INTEGER,
            default=10**10_000,
        )


def _resolve_schema_ref(schema: dict[str, object], node: dict[str, object]) -> dict[str, object]:
    while "$ref" in node:
        reference = cast(str, node["$ref"])
        assert reference.startswith("#/$defs/")
        definitions = cast(dict[str, dict[str, object]], schema["$defs"])
        node = definitions[reference.removeprefix("#/$defs/")]
    return node


def test_strategy_state_validation_schema_describes_the_json_object_input() -> None:
    state_schema = cast(
        dict[str, object], TypeAdapter(StrategyState).json_schema(mode="validation")
    )
    assert "_canonical_json" not in json.dumps(state_schema)
    assert _resolve_schema_ref(state_schema, state_schema)["type"] == "object"

    context_schema = cast(dict[str, object], StrategyContext.model_json_schema(mode="validation"))
    assert "_canonical_json" not in json.dumps(context_schema)
    properties = cast(dict[str, dict[str, object]], context_schema["properties"])
    assert _resolve_schema_ref(context_schema, properties["state"])["type"] == "object"


def test_context_state_type_errors_are_converted_to_validation_errors() -> None:
    with pytest.raises(ValidationError):
        StrategyContext.model_validate({"state": object()})


def test_strategy_state_instances_are_revalidated_at_contract_boundaries() -> None:
    untrusted = StrategyState.model_construct(
        root='{"nested":{"api_key":"DO-NOT-ECHO-THIS-CREDENTIAL"}}'
    )

    with pytest.raises(ValidationError):
        TypeAdapter(StrategyState).validate_python(untrusted)


@pytest.mark.parametrize(
    "root",
    [
        object(),
        b"{}",
        '{"same":1,"same":2}',
        '{"nested":{"api_key":"DO-NOT-ECHO-THIS-CREDENTIAL"}}',
    ],
)
def test_forged_state_instances_never_escape_raw_validator_errors(root: object) -> None:
    import trading_strategy_sdk as sdk

    untrusted = StrategyState.model_construct(root=root)
    with pytest.raises(ValidationError):
        TypeAdapter(StrategyState).validate_python(untrusted)
    with pytest.raises(ValidationError):
        untrusted.model_copy()
    with pytest.raises(ValidationError):
        sdk.StrategyOutput(signals=(), intents=(), next_state=untrusted)


def test_state_runtime_validation_matches_its_object_input_schema() -> None:
    with pytest.raises(ValidationError):
        StrategyState.model_validate("{}")
    with pytest.raises(ValidationError):
        StrategyState.model_validate_json('"{}"')


def test_state_item_budget_cannot_be_bypassed_by_a_container_subclass() -> None:
    class LyingList(list[JsonValue]):
        def __len__(self) -> int:
            return 0

    with pytest.raises(ValidationError):
        StrategyState.from_mapping({"safe": LyingList([0] * 20_000)})


def test_state_key_bounds_cannot_be_bypassed_by_a_string_subclass() -> None:
    class LyingString(str):
        length_calls = 0

        def __len__(self) -> int:
            type(self).length_calls += 1
            return 0

    malicious_key = LyingString("x" * (64 * 1024 + 1))
    with pytest.raises(ValidationError):
        StrategyState.from_mapping({malicious_key: True})
    assert LyingString.length_calls == 0


def test_state_mapping_and_type_failures_are_wrapped_without_input_leaks() -> None:
    secret = "DO-NOT-ECHO-MAPPING-SECRET"

    class ExplodingMapping(Mapping[str, JsonValue]):
        def __getitem__(self, key: str) -> JsonValue:
            raise KeyError(key)

        def __iter__(self) -> Iterator[str]:
            raise TypeError(secret)

        def __len__(self) -> int:
            return 1

    with pytest.raises(ValidationError) as mapping_error:
        StrategyState.from_mapping(ExplodingMapping())
    assert secret not in str(mapping_error.value)

    SecretType = type(secret, (), {})
    with pytest.raises(ValidationError) as type_error:
        StrategyState.from_mapping({"safe": cast(JsonValue, SecretType())})
    assert secret not in str(type_error.value)


def test_contract_copy_update_failures_are_wrapped_without_input_leaks() -> None:
    secret = "DO-NOT-ECHO-COPY-SECRET"

    class ExplodingUpdate(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            raise KeyError(key)

        def __iter__(self) -> Iterator[str]:
            raise TypeError(secret)

        def __len__(self) -> int:
            return 1

    class ExplodingDict(dict[str, object]):
        items_calls = 0

        def items(self) -> object:
            type(self).items_calls += 1
            raise RuntimeError(secret)

    parameter = ParameterSpec(name="lookback_bars", kind=ParameterType.INTEGER, default=20)
    for update in (ExplodingUpdate(), ExplodingDict(default=30)):
        with pytest.raises(ValidationError) as copy_error:
            parameter.model_copy(update=update)
        assert secret not in str(copy_error.value)
    assert ExplodingDict.items_calls == 0


def test_state_copy_rejects_mapping_subclasses_without_iterating_them() -> None:
    class RepeatingItems(dict[str, object]):
        items_calls = 0

        def items(self) -> Iterator[tuple[str, object]]:
            type(self).items_calls += 1
            for _ in range(20_000):
                yield ("root", {})

    with pytest.raises(ValidationError):
        StrategyState.empty().model_copy(update=RepeatingItems(root={}))
    assert RepeatingItems.items_calls == 0


def test_contract_copy_revalidates_forged_instances_before_dumping_or_copying() -> None:
    secret = "DO-NOT-ECHO-DEEPCOPY-SECRET"

    class EvilValue:
        def __deepcopy__(self, memo: object) -> object:
            del memo
            raise TypeError(secret)

    forged = ParameterSpec.model_construct(
        name="lookback_bars",
        kind=ParameterType.STRING,
        default=EvilValue(),
        minimum=None,
        maximum=None,
    )
    with pytest.raises(ValidationError) as copy_error:
        forged.model_copy(deep=True)
    assert secret not in str(copy_error.value)


def test_public_contract_decoders_reject_hostile_mapping_subclasses_without_iteration() -> None:
    import trading_strategy_sdk as sdk

    secret = "DO-NOT-ECHO-PUBLIC-MAPPING-SECRET"

    class HostileDict(dict[str, object]):
        items_calls = 0

        def items(self) -> object:
            type(self).items_calls += 1
            raise RuntimeError(secret)

    forged_output = sdk.StrategyOutput.model_construct(
        signals=(),
        intents=(
            HostileDict(
                kind="cancel_order",
                intent_id="cancel_1",
                order_id="order/opaque",
            ),
        ),
        next_state=sdk.StrategyState.empty(),
    )
    operations: tuple[Callable[[], object], ...] = (
        lambda: ParameterSpec.model_validate(
            HostileDict(name="lookback_bars", kind="integer", default=20)
        ),
        lambda: sdk.StrategyOutput.model_validate(
            HostileDict(signals=(), intents=(), next_state={})
        ),
        lambda: TypeAdapter(ParameterSpec).validate_python(
            HostileDict(name="lookback_bars", kind="integer", default=20)
        ),
        lambda: TypeAdapter(sdk.StrategyOutput).validate_python(
            HostileDict(signals=(), intents=(), next_state={})
        ),
        lambda: sdk.validate_order_intent(
            HostileDict(kind="cancel_order", intent_id="cancel_1", order_id="order/opaque")
        ),
        lambda: sdk.StrategyOutput.model_validate(
            {
                "signals": (),
                "intents": (
                    HostileDict(
                        kind="cancel_order",
                        intent_id="cancel_1",
                        order_id="order/opaque",
                    ),
                ),
                "next_state": {},
            }
        ),
        lambda: sdk.StrategyOutput.model_validate(forged_output),
    )
    for operation in operations:
        with pytest.raises(ValidationError) as validation_error:
            operation()
        assert secret not in str(validation_error.value)
    assert HostileDict.items_calls == 0


def test_public_contract_decoders_bound_mapping_subclass_iteration() -> None:
    class RepeatingItems(dict[str, object]):
        items_calls = 0

        def items(self) -> Iterator[tuple[str, object]]:
            type(self).items_calls += 1
            for _ in range(20_000):
                yield ("name", "lookback_bars")
                yield ("kind", "integer")
                yield ("default", 20)

    with pytest.raises(ValidationError):
        ParameterSpec.model_validate(RepeatingItems())
    assert RepeatingItems.items_calls == 0


def test_order_intent_discriminator_never_invokes_model_subclass_hooks() -> None:
    import trading_strategy_sdk as sdk

    secret = "DO-NOT-ECHO-INTENT-SUBCLASS-SECRET"

    class EvilCancel(sdk.CancelOrderIntent):
        def __getattribute__(self, name: str) -> object:
            if name == "kind":
                raise RuntimeError(secret)
            return super().__getattribute__(name)

    evil = EvilCancel.model_construct(
        kind="cancel_order",
        intent_id="cancel_1",
        order_id="order/opaque",
    )
    operations: tuple[Callable[[], object], ...] = (
        lambda: sdk.validate_order_intent(evil),
        lambda: sdk.StrategyOutput.model_validate(
            {"signals": (), "intents": (evil,), "next_state": {}}
        ),
        lambda: TypeAdapter(sdk.OrderIntent).validate_python(evil),
    )
    for operation in operations:
        with pytest.raises(ValidationError) as validation_error:
            operation()
        assert secret not in str(validation_error.value)


def test_plain_typed_bar_histories_are_not_charged_as_recursive_raw_input() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    first_close = datetime(2026, 1, 1, tzinfo=UTC)
    bars = tuple(
        _bar(subscription, first_close + timedelta(minutes=5 * index)) for index in range(1_000)
    )

    series = BarSeries(subscription=subscription, bars=bars)
    assert len(series.bars) == 1_000


@pytest.mark.parametrize("error_type", [TypeError, RuntimeError])
@pytest.mark.parametrize("target", ["position", "closed_bar"])
def test_timezone_callback_exceptions_are_wrapped_without_input_leaks(
    error_type: type[Exception], target: str
) -> None:
    from trading_strategy_sdk.positions import Position, PositionSide

    secret = "DO-NOT-ECHO-TIMEZONE-SECRET"

    class EvilTimezone(tzinfo):
        def utcoffset(self, value: datetime | None) -> timedelta:
            del value
            raise error_type(secret)

    malicious_time = datetime(2026, 1, 1, tzinfo=EvilTimezone())

    def construct_position() -> object:
        return Position(
            position_id="evil_timezone",
            symbol=Symbol.EURUSD,
            side=PositionSide.BUY,
            volume=Decimal("1"),
            average_price=Decimal("1"),
            opened_at=malicious_time,
        )

    def construct_bar() -> object:
        subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
        return ClosedBar(
            subscription=subscription,
            open_time=datetime(2025, 12, 31, 23, 55, tzinfo=UTC),
            close_time=malicious_time,
            bid=_ohlc("1"),
            ask=_ohlc("1"),
        )

    operation = construct_position if target == "position" else construct_bar
    with pytest.raises(ValidationError) as validation_error:
        operation()
    assert secret not in str(validation_error.value)


def test_extreme_timezone_normalization_errors_are_wrapped_by_pydantic() -> None:
    from trading_strategy_sdk.positions import Position, PositionSide

    overflowing = datetime.min.replace(tzinfo=timezone(timedelta(hours=14)))
    with pytest.raises(ValidationError):
        Position(
            position_id="extreme",
            symbol=Symbol.EURUSD,
            side=PositionSide.BUY,
            volume=Decimal("1"),
            average_price=Decimal("1"),
            opened_at=overflowing,
        )

    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    with pytest.raises(ValidationError):
        ClosedBar(
            subscription=subscription,
            open_time=overflowing,
            close_time=datetime(2026, 1, 1, tzinfo=UTC),
            bid=_ohlc("1"),
            ask=_ohlc("1"),
        )


def test_delayed_duplicate_events_share_identity_and_are_rejected() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    close_time = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    bar = _bar(subscription, close_time)
    immediate = BarClosedEvent(event_time=close_time, bar=bar)
    delayed = BarClosedEvent(event_time=close_time + timedelta(seconds=30), bar=bar)

    assert immediate.sort_key == delayed.sort_key
    with pytest.raises(ValueError, match="duplicate"):
        ordered_events((immediate, delayed))


def test_distinct_bar_closes_delivered_together_are_not_duplicate_events() -> None:
    subscription = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    first_close = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)
    close_times = tuple(first_close + timedelta(minutes=5 * offset) for offset in range(3))
    delivery_time = close_times[-1] + timedelta(seconds=20)
    events = tuple(
        BarClosedEvent(event_time=delivery_time, bar=_bar(subscription, close_time))
        for close_time in close_times
    )

    assert all(
        tuple(item.bar.close_time for item in ordered_events(candidate)) == close_times
        for candidate in permutations(events)
    )


def _canonical_spec(
    subscriptions: tuple[BarSubscription, ...],
    warmup: tuple[WarmupRequirement, ...],
    dependency_order: tuple[str, ...],
    hash_order: tuple[str, ...],
) -> StrategySpec:
    dependencies = {
        "alpha": DependencySpec(name="Alpha_Package", version="1.0", hashes=hash_order),
        "zeta": DependencySpec(name="zeta.package", version="2.0", hashes=hash_order),
    }
    return StrategySpec(
        subscriptions=subscriptions,
        warmup=warmup,
        triggers=(TriggerSpec(name="close", subscriptions=subscriptions),),
        synchronization=SynchronizationSpec(
            mode=SynchronizationMode.LATEST_CLOSED,
            required_subscriptions=subscriptions,
        ),
        entries=(RuleSpec(name="entry", description="Enter."),),
        exits=(RuleSpec(name="exit", description="Exit."),),
        position_mode=PositionMode.HEDGING,
        required_capabilities=frozenset({Capability.MULTI_SYMBOL_DATA, Capability.RETURN_FILLING}),
        order_types=frozenset({OrderType.BUY_LIMIT}),
        filling_policies=frozenset({OrderFilling.RETURN}),
        dependencies=tuple(dependencies[name] for name in dependency_order),
        disclosures=("Gap risk is disclosed.",),
        bounded_loss=BoundedLossSpec(
            stop_loss_required=True,
            gap_risk_disclosed=True,
            description="Every entry has a stop.",
        ),
    )


def test_semantically_unordered_spec_inputs_have_one_canonical_encoding() -> None:
    eurusd = BarSubscription(symbol=Symbol.EURUSD, timeframe=Timeframe.M5)
    xauusd = BarSubscription(symbol=Symbol.XAUUSD, timeframe=Timeframe.M5)
    subscriptions = (eurusd, xauusd)
    warmup = (
        WarmupRequirement(subscription=eurusd, bars=20),
        WarmupRequirement(subscription=xauusd, bars=10),
    )
    hashes = (f"sha256:{'1' * 64}", f"sha256:{'0' * 64}")

    encodings: set[str] = set()
    for subscription_order, warmup_order, dependency_order, hash_order in product(
        permutations(subscriptions),
        permutations(warmup),
        permutations(("alpha", "zeta")),
        permutations(hashes),
    ):
        spec = _canonical_spec(
            subscription_order,
            warmup_order,
            dependency_order,
            hash_order,
        )
        assert spec.subscriptions == subscriptions
        assert tuple(item.subscription for item in spec.warmup) == subscriptions
        assert tuple(item.name for item in spec.dependencies) == ("alpha-package", "zeta-package")
        assert all(item.hashes == tuple(sorted(hashes)) for item in spec.dependencies)
        encodings.add(spec.model_dump_json())

    assert len(encodings) == 1
