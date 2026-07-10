"""Validated server-side strategy specification contracts."""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Literal, Protocol, Self

from packaging.version import InvalidVersion, Version
from pydantic import (
    Field,
    StringConstraints,
    field_serializer,
    field_validator,
    model_validator,
)

from trading_strategy_sdk._model import (
    ContractModel as _ContractModel,
)
from trading_strategy_sdk._model import (
    Identifier,
    NonEmptyText,
    is_forbidden_strategy_data_name,
)
from trading_strategy_sdk.market import BarSubscription, Symbol, Timeframe
from trading_strategy_sdk.orders import OrderFilling, OrderType
from trading_strategy_sdk.positions import PositionMode

_PACKAGE_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
_SHA256 = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
ParameterValue = bool | int | float | str


class _Named(Protocol):
    @property
    def name(self) -> str: ...


class Capability(StrEnum):
    """Capabilities a platform must explicitly grant to a strategy version."""

    MULTI_SYMBOL_DATA = "multi_symbol_data"
    MULTI_TIMEFRAME_DATA = "multi_timeframe_data"
    DEPTH_OF_MARKET = "depth_of_market"
    FOK_FILLING = "fok_filling"
    IOC_FILLING = "ioc_filling"
    RETURN_FILLING = "return_filling"
    BOC_FILLING = "boc_filling"
    PLATFORM_OCO = "platform_oco"
    PLATFORM_BRACKETS = "platform_brackets"
    PLATFORM_TRAILING_STOP = "platform_trailing_stop"
    PLATFORM_BREAK_EVEN = "platform_break_even"
    PLATFORM_PARTIAL_EXITS = "platform_partial_exits"


class ParameterType(StrEnum):
    """JSON scalar types accepted by a strategy parameter."""

    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    STRING = "string"


class TriggerKind(StrEnum):
    """Release 1 trigger kinds."""

    BAR_CLOSE = "bar_close"


class SynchronizationMode(StrEnum):
    """How subscribed closed bars form a synchronized snapshot."""

    LATEST_CLOSED = "latest_closed"
    EXACT_CLOSE = "exact_close"


class WarmupRequirement(_ContractModel):
    """History required before a subscription may trigger entries."""

    subscription: BarSubscription
    bars: Annotated[int, Field(ge=0, le=1_000_000)]


class TriggerSpec(_ContractModel):
    """One named bar-close trigger over declared subscriptions."""

    name: Identifier
    subscriptions: Annotated[tuple[BarSubscription, ...], Field(min_length=1)]
    kind: TriggerKind = TriggerKind.BAR_CLOSE

    @field_validator("subscriptions")
    @classmethod
    def subscriptions_are_unique(
        cls, subscriptions: tuple[BarSubscription, ...]
    ) -> tuple[BarSubscription, ...]:
        if len(set(subscriptions)) != len(subscriptions):
            raise ValueError("trigger subscriptions must be unique")
        return tuple(sorted(subscriptions, key=lambda item: item.key))


class SynchronizationSpec(_ContractModel):
    """Subscriptions that must be present before a new entry is eligible."""

    mode: SynchronizationMode
    required_subscriptions: Annotated[tuple[BarSubscription, ...], Field(min_length=1)]

    @field_validator("required_subscriptions")
    @classmethod
    def subscriptions_are_unique(
        cls, subscriptions: tuple[BarSubscription, ...]
    ) -> tuple[BarSubscription, ...]:
        if len(set(subscriptions)) != len(subscriptions):
            raise ValueError("synchronization subscriptions must be unique")
        return tuple(sorted(subscriptions, key=lambda item: item.key))


class RuleSpec(_ContractModel):
    """A named entry or exit requirement; executable code is generated later."""

    name: Identifier
    description: NonEmptyText


class ParameterSpec(_ContractModel):
    """A bounded strategy-logic parameter, never an account-risk setting."""

    name: Identifier
    kind: ParameterType
    default: ParameterValue
    minimum: float | None = None
    maximum: float | None = None

    @model_validator(mode="after")
    def validate_parameter(self) -> Self:
        if is_forbidden_strategy_data_name(self.name):
            raise ValueError(
                "strategy parameters cannot define account or user risk policy, "
                "credentials, or execution sizing"
            )

        default_matches_kind = (
            (self.kind is ParameterType.BOOLEAN and type(self.default) is bool)
            or (self.kind is ParameterType.INTEGER and type(self.default) is int)
            or (self.kind is ParameterType.NUMBER and type(self.default) in {int, float})
            or (self.kind is ParameterType.STRING and type(self.default) is str)
        )
        if not default_matches_kind:
            raise ValueError(f"default does not match parameter kind {self.kind.value}")

        if self.kind not in {ParameterType.INTEGER, ParameterType.NUMBER}:
            if self.minimum is not None or self.maximum is not None:
                raise ValueError("only numeric parameters can declare minimum or maximum")
            return self

        try:
            numeric_default = float(self.default)
        except OverflowError as error:
            raise ValueError("numeric defaults must be finite") from error
        if not math.isfinite(numeric_default):
            raise ValueError("numeric defaults must be finite")
        if self.minimum is not None and not math.isfinite(self.minimum):
            raise ValueError("minimum must be finite")
        if self.maximum is not None and not math.isfinite(self.maximum):
            raise ValueError("maximum must be finite")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        if self.minimum is not None and numeric_default < self.minimum:
            raise ValueError("default is below minimum")
        if self.maximum is not None and numeric_default > self.maximum:
            raise ValueError("default is above maximum")
        return self


class DependencySpec(_ContractModel):
    """An exact PyPI dependency with approved artifact hashes."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    version: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    hashes: Annotated[tuple[str, ...], Field(min_length=1)]

    @field_validator("name")
    @classmethod
    def package_name_is_valid(cls, name: str) -> str:
        if _PACKAGE_NAME.fullmatch(name) is None:
            raise ValueError("dependency name must be a valid PyPI package name")
        return re.sub(r"[-_.]+", "-", name).lower()

    @field_validator("version")
    @classmethod
    def version_is_exact(cls, version: str) -> str:
        try:
            parsed = Version(version)
        except InvalidVersion as error:
            raise ValueError("dependency version must be an exact PEP 440 version") from error
        return str(parsed)

    @field_validator("hashes")
    @classmethod
    def hashes_are_sha256(cls, hashes: tuple[str, ...]) -> tuple[str, ...]:
        if any(_SHA256.fullmatch(value) is None for value in hashes):
            raise ValueError("dependency hashes must be SHA-256 values")
        normalized = tuple(value.lower() for value in hashes)
        if len(set(normalized)) != len(normalized):
            raise ValueError("dependency hashes must be unique")
        return tuple(sorted(normalized))


class BoundedLossSpec(_ContractModel):
    """Technical loss-bound requirements disclosed by a strategy."""

    stop_loss_required: bool
    gap_risk_disclosed: bool
    description: NonEmptyText

    @model_validator(mode="after")
    def requires_a_disclosed_stop(self) -> Self:
        if not self.stop_loss_required:
            raise ValueError("bounded-loss strategies must require a technical stop loss")
        if not self.gap_risk_disclosed:
            raise ValueError("bounded-loss strategies must disclose market gap risk")
        return self


_FILLING_CAPABILITIES: dict[OrderFilling, Capability] = {
    OrderFilling.FOK: Capability.FOK_FILLING,
    OrderFilling.IOC: Capability.IOC_FILLING,
    OrderFilling.RETURN: Capability.RETURN_FILLING,
    OrderFilling.BOC: Capability.BOC_FILLING,
}
_DOM_FILLINGS = frozenset({OrderFilling.FOK, OrderFilling.IOC, OrderFilling.BOC})


class StrategySpec(_ContractModel):
    """Hidden, validated input to strategy generation and review."""

    schema_version: Literal[1] = 1
    subscriptions: Annotated[tuple[BarSubscription, ...], Field(min_length=1)]
    warmup: Annotated[tuple[WarmupRequirement, ...], Field(min_length=1)]
    triggers: Annotated[tuple[TriggerSpec, ...], Field(min_length=1)]
    synchronization: SynchronizationSpec
    entries: Annotated[tuple[RuleSpec, ...], Field(min_length=1)]
    exits: Annotated[tuple[RuleSpec, ...], Field(min_length=1)]
    parameters: tuple[ParameterSpec, ...] = ()
    position_mode: PositionMode
    required_capabilities: frozenset[Capability]
    order_types: Annotated[frozenset[OrderType], Field(min_length=1)]
    filling_policies: Annotated[frozenset[OrderFilling], Field(min_length=1)]
    dependencies: tuple[DependencySpec, ...] = ()
    disclosures: Annotated[tuple[NonEmptyText, ...], Field(min_length=1)]
    bounded_loss: BoundedLossSpec

    @field_validator("subscriptions")
    @classmethod
    def order_subscriptions(
        cls, values: tuple[BarSubscription, ...]
    ) -> tuple[BarSubscription, ...]:
        return tuple(sorted(values, key=lambda item: item.key))

    @field_validator("warmup")
    @classmethod
    def order_warmup(cls, values: tuple[WarmupRequirement, ...]) -> tuple[WarmupRequirement, ...]:
        return tuple(sorted(values, key=lambda item: item.subscription.key))

    @field_validator("triggers")
    @classmethod
    def order_triggers(cls, values: tuple[TriggerSpec, ...]) -> tuple[TriggerSpec, ...]:
        return tuple(sorted(values, key=lambda item: item.name))

    @field_validator("parameters")
    @classmethod
    def order_parameters(cls, values: tuple[ParameterSpec, ...]) -> tuple[ParameterSpec, ...]:
        return tuple(sorted(values, key=lambda item: item.name))

    @field_validator("dependencies")
    @classmethod
    def order_dependencies(cls, values: tuple[DependencySpec, ...]) -> tuple[DependencySpec, ...]:
        return tuple(sorted(values, key=lambda item: (item.name, item.version)))

    @field_serializer("required_capabilities")
    def serialize_capabilities(self, values: frozenset[Capability]) -> tuple[str, ...]:
        return tuple(sorted(value.value for value in values))

    @field_serializer("order_types")
    def serialize_order_types(self, values: frozenset[OrderType]) -> tuple[int, ...]:
        return tuple(sorted(value.value for value in values))

    @field_serializer("filling_policies")
    def serialize_filling_policies(self, values: frozenset[OrderFilling]) -> tuple[int, ...]:
        return tuple(sorted(value.value for value in values))

    @property
    def symbols(self) -> tuple[Symbol, ...]:
        """Return declared symbols in stable lexical order."""
        return tuple(
            sorted({item.symbol for item in self.subscriptions}, key=lambda item: item.value)
        )

    @property
    def timeframes(self) -> tuple[Timeframe, ...]:
        """Return declared timeframes in stable duration order."""
        return tuple(
            sorted({item.timeframe for item in self.subscriptions}, key=lambda item: item.minutes)
        )

    @model_validator(mode="after")
    def validate_references_and_capabilities(self) -> Self:
        declared = set(self.subscriptions)
        if len(declared) != len(self.subscriptions):
            raise ValueError("subscriptions must be unique")

        warmup_subscriptions = [item.subscription for item in self.warmup]
        if len(set(warmup_subscriptions)) != len(warmup_subscriptions):
            raise ValueError("each subscription must have exactly one warmup requirement")
        if set(warmup_subscriptions) != declared:
            raise ValueError("warmup requirements must cover every declared subscription")

        for trigger in self.triggers:
            if not set(trigger.subscriptions) <= declared:
                raise ValueError("trigger references an undeclared subscription")
        if len({item.name for item in self.triggers}) != len(self.triggers):
            raise ValueError("trigger names must be unique")

        if set(self.synchronization.required_subscriptions) != declared:
            raise ValueError("synchronization must require every declared subscription")

        self._require_unique_names("entry rule", self.entries)
        self._require_unique_names("exit rule", self.exits)
        self._require_unique_names("parameter", self.parameters)
        self._require_unique_names("dependency", self.dependencies)
        if len(set(self.disclosures)) != len(self.disclosures):
            raise ValueError("disclosures must be unique")

        required = set(self.required_capabilities)
        if len(self.symbols) > 1 and Capability.MULTI_SYMBOL_DATA not in required:
            raise ValueError("multi-symbol specs must declare MULTI_SYMBOL_DATA")
        if len(self.timeframes) > 1 and Capability.MULTI_TIMEFRAME_DATA not in required:
            raise ValueError("multi-timeframe specs must declare MULTI_TIMEFRAME_DATA")

        for filling in self.filling_policies:
            capability = _FILLING_CAPABILITIES[filling]
            if capability not in required:
                raise ValueError(f"{filling.name} requires capability {capability.name}")
        if self.filling_policies & _DOM_FILLINGS and Capability.DEPTH_OF_MARKET not in required:
            raise ValueError("FOK, IOC, and BOC require DEPTH_OF_MARKET")
        if (
            OrderType.CLOSE_BY in self.order_types
            and self.position_mode is not PositionMode.HEDGING
        ):
            raise ValueError("CLOSE_BY order type requires HEDGING position mode")
        return self

    @staticmethod
    def _require_unique_names(label: str, values: Iterable[_Named]) -> None:
        names = [value.name for value in values]
        if len(set(names)) != len(names):
            raise ValueError(f"{label} names must be unique")
