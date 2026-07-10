"""Internal validation primitives shared by SDK contracts."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Collection, Iterable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Self, cast

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, TypeAdapter, model_validator

NonEmptyText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=2_000),
]
Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_]*$",
    ),
]
OpaqueId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
]
Price = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
NonNegativeDecimal = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]
PositiveDecimal = Annotated[Decimal, Field(gt=0, allow_inf_nan=False)]
FiniteDecimal = Annotated[Decimal, Field(allow_inf_nan=False)]

_NAME_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_NAME_SEPARATOR = re.compile(r"[^a-z0-9]+")
_CONFUSABLE_ASCII = str.maketrans(
    {
        "\u0430": "a",
        "\u0435": "e",
        "\u0456": "i",
        "\u0458": "j",
        "\u043e": "o",
        "\u0440": "p",
        "\u0441": "c",
        "\u0445": "x",
        "\u0443": "y",
        "\u0391": "A",
        "\u0392": "B",
        "\u0395": "E",
        "\u0399": "I",
        "\u039a": "K",
        "\u039c": "M",
        "\u039d": "N",
        "\u039f": "O",
        "\u03a1": "P",
        "\u03a4": "T",
        "\u03a7": "X",
        "\u03a5": "Y",
        "\u0396": "Z",
        "\u03b1": "a",
        "\u03b9": "i",
        "\u03ba": "k",
        "\u03bf": "o",
        "\u03c1": "p",
        "\u03c4": "t",
        "\u03c5": "y",
        "\u03c7": "x",
    }
)
_FORBIDDEN_DATA_TOKENS = frozenset(
    {
        "account",
        "allocation",
        "auth",
        "authorization",
        "balance",
        "bearer",
        "budget",
        "cash",
        "capital",
        "contract",
        "contracts",
        "cookie",
        "credential",
        "credentials",
        "drawdown",
        "equity",
        "exposure",
        "funds",
        "jwt",
        "leverage",
        "login",
        "lot",
        "lots",
        "margin",
        "money",
        "notional",
        "passphrase",
        "passwd",
        "password",
        "pwd",
        "qty",
        "quantities",
        "quantity",
        "risk",
        "secret",
        "shares",
        "sizing",
        "stake",
        "token",
        "unit",
        "units",
        "username",
        "volume",
    }
)
_FORBIDDEN_COMPACT_DATA_NAMES = frozenset(
    {
        "accountbalance",
        "accountequity",
        "accountnumber",
        "accountvalue",
        "accesstoken",
        "apikey",
        "authkey",
        "authtoken",
        "bearertoken",
        "capitalatrisk",
        "clientid",
        "clientsecret",
        "dailylosslimit",
        "finallot",
        "funds",
        "lotsize",
        "maxdailyloss",
        "maxloss",
        "maxopenrisk",
        "maxpositions",
        "maxtrades",
        "openpositionlimit",
        "orderquantity",
        "ordersize",
        "positionquantity",
        "positionsize",
        "privatekey",
        "refreshtoken",
        "riskamount",
        "riskbudget",
        "risklimit",
        "riskpct",
        "riskpercent",
        "riskpercentage",
        "riskpertrade",
        "riskpolicy",
        "secretkey",
        "size",
        "tradesize",
        "userpolicy",
        "userriskpolicy",
    }
)
_SIZING_QUALIFIERS = frozenset(
    {
        "contract",
        "contracts",
        "final",
        "lot",
        "lots",
        "order",
        "orders",
        "position",
        "positions",
        "trade",
        "trades",
        "unit",
        "units",
    }
)
_SIZING_VALUE_TOKENS = frozenset({"amount", "count", "limit", "max", "size", "weight"})
_KEY_QUALIFIERS = frozenset({"access", "api", "auth", "client", "private", "secret"})
_ACCOUNT_DATA_QUALIFIERS = frozenset({"balance", "equity", "id", "login", "number", "value"})
_LOSS_POLICY_QUALIFIERS = frozenset({"daily", "limit", "max", "policy"})
_FORBIDDEN_COMPACT_AFFIXES = frozenset(
    {
        "account",
        "allocation",
        "auth",
        "authorization",
        "balance",
        "bearer",
        "capital",
        "contract",
        "contracts",
        "credential",
        "credentials",
        "drawdown",
        "equity",
        "exposure",
        "leverage",
        "margin",
        "notional",
        "passphrase",
        "password",
        "quantity",
        "secret",
        "sizing",
        "stake",
        "token",
        "volume",
    }
)
_COMPACT_SIZING_PREFIXES = frozenset({"final", "order", "position", "trade"})
_COMPACT_SIZING_SUFFIXES = frozenset(
    {"amount", "contracts", "count", "limit", "qty", "quantity", "size", "units", "weight"}
)
_COMPACT_MAX_SIZING_SUFFIXES = frozenset(
    {"contracts", "lots", "orders", "positions", "trades", "units"}
)
_MODEL_COPY_UPDATE_ADAPTER = TypeAdapter[dict[str, Any]](
    dict[str, Any],
    config=ConfigDict(hide_input_in_errors=True, strict=True),
)
_MAX_VALIDATION_CONTAINER_DEPTH = 32
_MAX_VALIDATION_CONTAINER_ITEMS = 10_000


def has_plain_bounded_validation_containers(value: object) -> bool:
    """Reject hook-bearing or unbounded containers before Pydantic can iterate them."""
    budget = [0]
    active: set[int] = set()

    def inspect(candidate: object, depth: int, *, scan_model: bool = False) -> bool:
        if depth > _MAX_VALIDATION_CONTAINER_DEPTH:
            return False
        if isinstance(candidate, BaseModel):
            if not scan_model:
                return True
            try:
                field_storage: object = object.__getattribute__(candidate, "__dict__")
            except Exception:
                return False
            if type(field_storage) is not dict:
                return False
            return inspect(cast(dict[object, object], field_storage), depth + 1)

        if type(candidate) is dict:
            mapping = cast(dict[object, object], candidate)
            identity = id(mapping)
            if identity in active:
                return False
            budget[0] += len(mapping)
            if budget[0] > _MAX_VALIDATION_CONTAINER_ITEMS:
                return False
            active.add(identity)
            try:
                return all(
                    inspect(key, depth + 1) and inspect(item, depth + 1)
                    for key, item in mapping.items()
                )
            finally:
                active.remove(identity)
        if isinstance(candidate, Mapping):
            return False

        collection: Collection[object] | None = None
        if type(candidate) is list:
            collection = cast(list[object], candidate)
        elif type(candidate) is tuple:
            collection = cast(tuple[object, ...], candidate)
        elif type(candidate) is set:
            collection = cast(set[object], candidate)
        elif type(candidate) is frozenset:
            collection = cast(frozenset[object], candidate)
        elif isinstance(candidate, (list, tuple, set, frozenset)):
            return False
        if collection is not None:
            identity = id(collection)
            if identity in active:
                return False
            budget[0] += len(collection)
            if budget[0] > _MAX_VALIDATION_CONTAINER_ITEMS:
                return False
            active.add(identity)
            try:
                return all(inspect(item, depth + 1) for item in collection)
            finally:
                active.remove(identity)

        return not (
            isinstance(candidate, Iterable) and not isinstance(candidate, (str, bytes, bytearray))
        )

    return inspect(value, 0, scan_model=True)


def is_forbidden_strategy_data_name(name: str) -> bool:
    """Whether a field name aliases user risk, credentials, or execution sizing."""
    normalized = unicodedata.normalize("NFKC", name).translate(_CONFUSABLE_ASCII).strip()
    normalized = "".join(
        character for character in normalized if unicodedata.category(character) != "Cf"
    )
    separated = _NAME_BOUNDARY.sub("_", normalized)
    tokens = tuple(token for token in _NAME_SEPARATOR.split(separated.casefold()) if token)
    token_set = frozenset(tokens)
    compact = "".join(tokens)
    return (
        bool(token_set & _FORBIDDEN_DATA_TOKENS)
        or compact in _FORBIDDEN_DATA_TOKENS
        or compact in _FORBIDDEN_COMPACT_DATA_NAMES
        or any(
            compact.startswith(alias) or compact.endswith(alias)
            for alias in _FORBIDDEN_COMPACT_AFFIXES
        )
        or compact.startswith("risk")
        or compact.endswith("atrisk")
        or (
            any(compact.startswith(prefix) for prefix in _COMPACT_SIZING_PREFIXES)
            and any(compact.endswith(suffix) for suffix in _COMPACT_SIZING_SUFFIXES)
        )
        or (
            compact.startswith("max")
            and any(compact.endswith(suffix) for suffix in _COMPACT_MAX_SIZING_SUFFIXES)
        )
        or (bool(token_set & _SIZING_VALUE_TOKENS) and bool(token_set & _SIZING_QUALIFIERS))
        or ("key" in token_set and bool(token_set & _KEY_QUALIFIERS))
        or ("account" in token_set and bool(token_set & _ACCOUNT_DATA_QUALIFIERS))
        or ("loss" in token_set and bool(token_set & _LOSS_POLICY_QUALIFIERS))
    )


class ContractModel(BaseModel):
    """Immutable strict-boundary model used throughout the public SDK."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
        validate_default=True,
    )

    @model_validator(mode="before")
    @classmethod
    def input_uses_plain_bounded_containers(cls, value: object) -> object:
        """Reject hook-bearing or unbounded containers before field parsing."""
        if not has_plain_bounded_validation_containers(value):
            raise ValueError("contract input must use plain bounded containers")
        return value

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        """Copy a contract while revalidating every requested update."""
        validated_self = self.__class__.model_validate(self)
        values = validated_self.model_dump(round_trip=True)
        if deep:
            values = deepcopy(values)
        if update is not None:
            if type(update) is not dict:
                _MODEL_COPY_UPDATE_ADAPTER.validate_python(None)
                raise AssertionError("invalid update unexpectedly validated")
            values.update(_MODEL_COPY_UPDATE_ADAPTER.validate_python(cast(dict[str, Any], update)))
        return self.__class__.model_validate(values)

    def canonical_bytes(self) -> bytes:
        """Return deterministic UTF-8 JSON bytes for this immutable contract."""
        return canonical_bytes(self)

    def sha256_digest(self) -> str:
        """Return the prefixed SHA-256 identity of :meth:`canonical_bytes`."""
        return sha256_digest(self)


def canonical_bytes(value: ContractModel) -> bytes:
    """Encode an immutable SDK contract as compact, key-sorted UTF-8 JSON."""
    validated = value.__class__.model_validate(value)
    payload = validated.model_dump(mode="json")
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return encoded.encode("utf-8")


def sha256_digest(value: ContractModel) -> str:
    """Return a lowercase ``sha256:<hex>`` identity for an immutable contract."""
    return f"sha256:{hashlib.sha256(canonical_bytes(value)).hexdigest()}"


def as_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC and reject naive values."""
    try:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("times must be timezone-aware UTC values")
        return value.astimezone(UTC)
    except Exception as error:
        raise ValueError("times must be representable timezone-aware UTC values") from error
