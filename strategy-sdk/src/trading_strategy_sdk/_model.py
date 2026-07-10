"""Internal validation primitives shared by SDK contracts."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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


class ContractModel(BaseModel):
    """Immutable strict-boundary model used throughout the public SDK."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
        validate_default=True,
    )

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> Self:
        """Copy a contract while revalidating every requested update."""
        values = self.model_dump(round_trip=True)
        if deep:
            values = deepcopy(values)
        if update is not None:
            values.update(update)
        return self.__class__.model_validate(values)


def as_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC and reject naive values."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("times must be timezone-aware UTC values")
    return value.astimezone(UTC)
