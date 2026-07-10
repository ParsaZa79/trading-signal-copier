"""Explicit, portable strategy state with canonical JSON serialization."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Annotated, Any, Literal, NoReturn, Self, cast

from pydantic import (
    AfterValidator,
    BeforeValidator,
    ConfigDict,
    Field,
    RootModel,
    TypeAdapter,
    model_serializer,
)

from trading_strategy_sdk._model import is_forbidden_strategy_data_name

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

_MAX_STATE_BYTES = 64 * 1024
_MAX_STATE_DEPTH = 16
_MAX_STATE_ITEMS = 10_000


class _CanonicalJson(str):
    """Marker distinguishing validated storage from public string input."""


def _reserve_items(budget: list[int], count: int) -> None:
    budget[0] += count
    if budget[0] > _MAX_STATE_ITEMS:
        raise ValueError("strategy state exceeds the cumulative item limit")


def _reserve_bytes(budget: list[int], count: int) -> None:
    budget[1] += count
    if budget[1] > _MAX_STATE_BYTES:
        raise ValueError("strategy state exceeds the canonical byte limit")


def _serialized_string_size(value: str) -> int:
    if len(value) > _MAX_STATE_BYTES:
        raise ValueError("strategy state string exceeds the byte limit")
    serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(serialized) > _MAX_STATE_BYTES:
        raise ValueError("strategy state string exceeds the byte limit")
    return len(serialized.encode("utf-8"))


def _normalize_json(
    value: object,
    *,
    path: str = "$",
    depth: int = 1,
    budget: list[int] | None = None,
) -> JsonValue:
    if budget is None:
        budget = [0, 0]
    if value is None:
        _reserve_bytes(budget, 4)
        return None
    if type(value) is bool:
        _reserve_bytes(budget, 4 if value else 5)
        return value
    if type(value) is int:
        estimated_digits = max(1, (abs(value).bit_length() * 30_103) // 100_000 + 1)
        if estimated_digits > _MAX_STATE_BYTES:
            raise ValueError("strategy state integer exceeds the byte limit")
        try:
            serialized_integer = str(value)
        except ValueError as error:
            raise ValueError("strategy state integer cannot be encoded") from error
        _reserve_bytes(budget, len(serialized_integer))
        return value
    if type(value) is str:
        _reserve_bytes(budget, _serialized_string_size(value))
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite numbers")
        _reserve_bytes(budget, len(repr(value)))
        return value
    if type(value) is list:
        if depth > _MAX_STATE_DEPTH:
            raise ValueError("strategy state exceeds the nesting depth limit")
        items = cast(list[object], value)
        _reserve_items(budget, len(items))
        _reserve_bytes(budget, 2 + max(0, len(items) - 1))
        return [
            _normalize_json(
                item,
                path=f"{path}[{index}]",
                depth=depth + 1,
                budget=budget,
            )
            for index, item in enumerate(items)
        ]
    if type(value) is dict:
        items = cast(dict[object, object], value)
        return _normalize_object(
            items,
            path=path,
            depth=depth,
            budget=budget,
            item_count=len(items),
        )
    if isinstance(value, Mapping):
        items = cast(Mapping[object, object], value)
        return _normalize_object(
            items,
            path=path,
            depth=depth,
            budget=budget,
            item_count=None,
        )
    raise ValueError(f"{path} contains a non-JSON value")


def _normalize_object(
    items: Mapping[object, object],
    *,
    path: str,
    depth: int,
    budget: list[int],
    item_count: int | None,
) -> JsonObject:
    if depth > _MAX_STATE_DEPTH:
        raise ValueError("strategy state exceeds the nesting depth limit")
    if item_count is None:
        _reserve_bytes(budget, 2)
    else:
        _reserve_items(budget, item_count)
        _reserve_bytes(budget, 2 + max(0, item_count - 1))
    normalized: JsonObject = {}
    for key, item in items.items():
        if item_count is None:
            _reserve_items(budget, 1)
            if normalized:
                _reserve_bytes(budget, 1)
        if type(key) is not str:
            raise ValueError(f"{path} contains a non-string object key")
        if not key:
            raise ValueError("strategy state keys cannot be empty")
        if len(key) > _MAX_STATE_BYTES:
            raise ValueError("strategy state key exceeds the byte limit")
        if not key.isascii():
            raise ValueError("strategy state keys must use portable ASCII characters")
        if key in normalized:
            raise ValueError("strategy state contains duplicate object keys")
        _reserve_bytes(budget, _serialized_string_size(key) + 1)
        if is_forbidden_strategy_data_name(key):
            raise ValueError("strategy state cannot contain risk, credential, or sizing keys")
        normalized[key] = _normalize_json(
            item,
            path=f"{path}.<field>",
            depth=depth + 1,
            budget=budget,
        )
    return normalized


def _reject_constant(_value: str) -> NoReturn:
    raise ValueError("non-finite JSON numbers are not allowed")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object keys are not allowed")
        result[key] = value
    return result


def _decode_json_object(value: object) -> JsonObject:
    if type(value) is not str:
        raise ValueError("serialized strategy state must be a JSON string")
    serialized = value
    if len(serialized) > _MAX_STATE_BYTES:
        raise ValueError("serialized strategy state exceeds the byte limit")
    if len(serialized.encode("utf-8")) > _MAX_STATE_BYTES:
        raise ValueError("serialized strategy state exceeds the byte limit")
    try:
        parsed: object = json.loads(
            serialized,
            parse_constant=_reject_constant,
            object_pairs_hook=_unique_object,
        )
    except (json.JSONDecodeError, RecursionError, ValueError) as error:
        raise ValueError("serialized strategy state is not valid JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("strategy state must be a JSON object")
    return cast(JsonObject, parsed)


def _encode_object(value: JsonObject) -> str:
    try:
        encoded = json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (RecursionError, TypeError, ValueError) as error:
        raise ValueError("strategy state cannot be encoded as canonical JSON") from error
    if len(encoded.encode("utf-8")) > _MAX_STATE_BYTES:
        raise ValueError("strategy state exceeds the canonical byte limit")
    return encoded


def _state_input_to_canonical(value: object) -> str:
    try:
        if isinstance(value, _CanonicalJson):
            value = _decode_json_object(str(value))
        if not isinstance(value, Mapping):
            raise ValueError("strategy state input must be a JSON object")
        normalized = _normalize_json(cast(Mapping[object, object], value))
    except Exception as error:
        raise ValueError("strategy state input is not a valid bounded JSON object") from error
    if not isinstance(normalized, dict):
        raise ValueError("strategy state must be a JSON object")
    return _encode_object(normalized)


type _CanonicalState = Annotated[
    str,
    BeforeValidator(_state_input_to_canonical, json_schema_input_type=JsonObject),
    AfterValidator(_CanonicalJson),
]
type _DecodedState = Annotated[
    object,
    BeforeValidator(_decode_json_object, json_schema_input_type=str),
]

_DECODED_STATE_ADAPTER = TypeAdapter[object](
    _DecodedState,
    config=ConfigDict(hide_input_in_errors=True, strict=True),
)
_STATE_COPY_UPDATE_ADAPTER = TypeAdapter[dict[Literal["root"], object]](
    dict[Literal["root"], object],
    config=ConfigDict(hide_input_in_errors=True, strict=True),
)
_STATE_KEY_ADAPTER = TypeAdapter[str](
    str,
    config=ConfigDict(hide_input_in_errors=True, strict=True),
)


class StrategyState(RootModel[_CanonicalState]):
    """A deeply immutable state value backed by canonical JSON."""

    model_config = ConfigDict(
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        strict=True,
        validate_default=True,
    )

    root: _CanonicalState = Field(repr=False)

    @model_serializer(mode="plain")
    def serialize_state(self) -> JsonObject:
        """Serialize state as the JSON object accepted at validation boundaries."""
        return self.to_mapping()

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        """Copy state while revalidating any replacement root object."""
        del deep  # Canonical string storage has no mutable nested values to copy.
        validated_self = self.__class__.model_validate(self)
        candidate: object = validated_self.to_mapping()
        if update is not None:
            if type(update) is not dict:
                _STATE_COPY_UPDATE_ADAPTER.validate_python(None)
                raise AssertionError("invalid update unexpectedly validated")
            validated = _STATE_COPY_UPDATE_ADAPTER.validate_python(
                cast(dict[Literal["root"], object], update)
            )
            candidate = validated.get("root", candidate)
        return self.__class__.model_validate(candidate)

    @classmethod
    def empty(cls) -> Self:
        """Create empty strategy state."""
        return cls.model_validate({})

    @classmethod
    def from_mapping(cls, value: Mapping[str, JsonValue]) -> Self:
        """Validate and copy a mapping into immutable state."""
        return cls.model_validate(value)

    @classmethod
    def from_json(cls, value: str) -> Self:
        """Validate a serialized JSON object and canonicalize it."""
        decoded: object = _DECODED_STATE_ADAPTER.validate_python(value)
        return cls.model_validate(decoded)

    def to_mapping(self) -> JsonObject:
        """Return a detached mutable JSON-compatible copy."""
        return cast(JsonObject, json.loads(self.root))

    def to_json(self) -> str:
        """Return canonical JSON with stable key ordering."""
        return str(self.root)

    def with_value(self, key: str, value: JsonValue) -> Self:
        """Return new state with one top-level value replaced."""
        validated_key = _STATE_KEY_ADAPTER.validate_python(key)
        updated = self.to_mapping()
        updated[validated_key] = value
        return self.from_mapping(updated)
