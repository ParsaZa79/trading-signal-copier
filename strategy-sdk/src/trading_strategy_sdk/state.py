"""Explicit, portable strategy state with canonical JSON serialization."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import NoReturn, cast

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]


def _normalize_json(value: object, path: str = "$") -> JsonValue:
    if value is None or type(value) in {bool, int, str}:
        return cast(JsonScalar, value)
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path} must contain only finite numbers")
        return value
    if isinstance(value, list):
        items = cast(list[object], value)
        return [_normalize_json(item, f"{path}[{index}]") for index, item in enumerate(items)]
    if isinstance(value, dict):
        items = cast(dict[object, object], value)
        normalized: JsonObject = {}
        for key, item in items.items():
            if not isinstance(key, str):
                raise TypeError(f"{path} contains a non-string object key")
            normalized[key] = _normalize_json(item, f"{path}.{key}")
        return normalized
    raise TypeError(f"{path} contains non-JSON value {type(value).__name__}")


def _reject_constant(value: str) -> NoReturn:
    raise ValueError(f"non-finite JSON number is not allowed: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _decode_object(value: str) -> JsonObject:
    parsed: object = json.loads(
        value,
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )
    normalized = _normalize_json(parsed)
    if not isinstance(normalized, dict):
        raise ValueError("strategy state must be a JSON object")
    return normalized


def _encode_object(value: JsonObject) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )


@dataclass(frozen=True, slots=True)
class StrategyState:
    """A deeply immutable state value backed by canonical JSON."""

    _canonical_json: str = field(repr=False)

    def __post_init__(self) -> None:
        canonical = _encode_object(_decode_object(self._canonical_json))
        object.__setattr__(self, "_canonical_json", canonical)

    @classmethod
    def empty(cls) -> StrategyState:
        """Create empty strategy state."""
        return cls("{}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, JsonValue]) -> StrategyState:
        """Validate and copy a mapping into immutable state."""
        normalized = _normalize_json(dict(value))
        if not isinstance(normalized, dict):  # pragma: no cover - fixed by the signature
            raise TypeError("strategy state must be an object")
        return cls(_encode_object(normalized))

    @classmethod
    def from_json(cls, value: str) -> StrategyState:
        """Validate a serialized JSON object and canonicalize it."""
        return cls(_encode_object(_decode_object(value)))

    def to_mapping(self) -> JsonObject:
        """Return a detached mutable JSON-compatible copy."""
        return _decode_object(self._canonical_json)

    def to_json(self) -> str:
        """Return canonical JSON with stable key ordering."""
        return self._canonical_json

    def with_value(self, key: str, value: JsonValue) -> StrategyState:
        """Return new state with one top-level value replaced."""
        if not key:
            raise ValueError("state key cannot be empty")
        updated = self.to_mapping()
        updated[key] = _normalize_json(value, f"$.{key}")
        return StrategyState.from_mapping(updated)
