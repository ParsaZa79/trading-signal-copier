"""Typed, strategy-visible outcomes for platform lifecycle operations."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self, final

from pydantic import Field, StringConstraints, TypeAdapter, field_validator, model_validator

from trading_strategy_sdk._model import ContractModel, Identifier, OpaqueId, as_utc

_UNREDACTED_ASSIGNMENT = re.compile(
    r"(?i)(?:password|secret|token|credential|authorization|cookie|api[_-]?key)\s*[:=]"
)
RedactedReason = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class LifecycleOperation(StrEnum):
    """Closed operation vocabulary for post-placement lifecycle outcomes."""

    MODIFY_ORDER = "modify_order"
    CANCEL_ORDER = "cancel_order"
    PROTECT_POSITION = "protect_position"
    CLOSE_POSITION_FULL = "close_position_full"
    CLOSE_POSITION_PARTIAL = "close_position_partial"
    CLOSE_BY = "close_by"
    MODIFY_OCO = "modify_oco"
    CANCEL_OCO = "cancel_oco"
    MODIFY_MANAGED_EXIT = "modify_managed_exit"
    CLEAR_MANAGED_EXIT = "clear_managed_exit"


class LifecycleStatus(StrEnum):
    """Terminal status of a lifecycle request."""

    SUCCEEDED = "succeeded"
    REJECTED = "rejected"
    FAILED = "failed"


class _LifecycleResult(ContractModel):
    intent_id: Identifier
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def created_at_is_utc(cls, value: datetime) -> datetime:
        return as_utc(value)


@final
class OrderModifiedResult(_LifecycleResult):
    kind: Literal["order_modified_result"] = "order_modified_result"
    operation: Literal[LifecycleOperation.MODIFY_ORDER] = LifecycleOperation.MODIFY_ORDER
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    order_id: OpaqueId


@final
class OrderCancelledResult(_LifecycleResult):
    kind: Literal["order_cancelled_result"] = "order_cancelled_result"
    operation: Literal[LifecycleOperation.CANCEL_ORDER] = LifecycleOperation.CANCEL_ORDER
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    order_id: OpaqueId


@final
class PositionProtectedResult(_LifecycleResult):
    kind: Literal["position_protected_result"] = "position_protected_result"
    operation: Literal[LifecycleOperation.PROTECT_POSITION] = LifecycleOperation.PROTECT_POSITION
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    position_id: OpaqueId
    managed_exit_plan_id: OpaqueId | None = None


@final
class FullPositionCloseResult(_LifecycleResult):
    kind: Literal["full_position_close_result"] = "full_position_close_result"
    operation: Literal[LifecycleOperation.CLOSE_POSITION_FULL] = (
        LifecycleOperation.CLOSE_POSITION_FULL
    )
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    position_id: OpaqueId


@final
class PartialPositionCloseResult(_LifecycleResult):
    kind: Literal["partial_position_close_result"] = "partial_position_close_result"
    operation: Literal[LifecycleOperation.CLOSE_POSITION_PARTIAL] = (
        LifecycleOperation.CLOSE_POSITION_PARTIAL
    )
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    position_id: OpaqueId
    fraction: Annotated[Decimal, Field(gt=0, lt=1, allow_inf_nan=False)]


@final
class CloseByResult(_LifecycleResult):
    kind: Literal["close_by_result"] = "close_by_result"
    operation: Literal[LifecycleOperation.CLOSE_BY] = LifecycleOperation.CLOSE_BY
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    position_id: OpaqueId
    opposite_position_id: OpaqueId

    @model_validator(mode="after")
    def positions_are_distinct(self) -> Self:
        if self.position_id == self.opposite_position_id:
            raise ValueError("close-by result position IDs must be different")
        return self


@final
class OcoModifiedResult(_LifecycleResult):
    kind: Literal["oco_modified_result"] = "oco_modified_result"
    operation: Literal[LifecycleOperation.MODIFY_OCO] = LifecycleOperation.MODIFY_OCO
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    oco_group_id: OpaqueId


@final
class OcoCancelledResult(_LifecycleResult):
    kind: Literal["oco_cancelled_result"] = "oco_cancelled_result"
    operation: Literal[LifecycleOperation.CANCEL_OCO] = LifecycleOperation.CANCEL_OCO
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    oco_group_id: OpaqueId


@final
class ManagedExitModifiedResult(_LifecycleResult):
    kind: Literal["managed_exit_modified_result"] = "managed_exit_modified_result"
    operation: Literal[LifecycleOperation.MODIFY_MANAGED_EXIT] = (
        LifecycleOperation.MODIFY_MANAGED_EXIT
    )
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    managed_exit_plan_id: OpaqueId


@final
class ManagedExitClearedResult(_LifecycleResult):
    kind: Literal["managed_exit_cleared_result"] = "managed_exit_cleared_result"
    operation: Literal[LifecycleOperation.CLEAR_MANAGED_EXIT] = (
        LifecycleOperation.CLEAR_MANAGED_EXIT
    )
    status: Literal[LifecycleStatus.SUCCEEDED] = LifecycleStatus.SUCCEEDED
    managed_exit_plan_id: OpaqueId


class _UnsuccessfulLifecycleResult(_LifecycleResult):
    operation: LifecycleOperation
    order_id: OpaqueId | None = None
    position_id: OpaqueId | None = None
    opposite_position_id: OpaqueId | None = None
    oco_group_id: OpaqueId | None = None
    managed_exit_plan_id: OpaqueId | None = None
    reason: RedactedReason

    @field_validator("reason")
    @classmethod
    def reason_is_redacted(cls, value: str) -> str:
        if _UNREDACTED_ASSIGNMENT.search(value) is not None or any(
            ord(character) < 32 for character in value
        ):
            raise ValueError("lifecycle reason must be a bounded redacted summary")
        return value

    @model_validator(mode="after")
    def target_matches_operation(self) -> Self:
        present = {
            name
            for name in (
                "order_id",
                "position_id",
                "opposite_position_id",
                "oco_group_id",
                "managed_exit_plan_id",
            )
            if getattr(self, name) is not None
        }
        expected = {
            LifecycleOperation.MODIFY_ORDER: {"order_id"},
            LifecycleOperation.CANCEL_ORDER: {"order_id"},
            LifecycleOperation.PROTECT_POSITION: {"position_id"},
            LifecycleOperation.CLOSE_POSITION_FULL: {"position_id"},
            LifecycleOperation.CLOSE_POSITION_PARTIAL: {"position_id"},
            LifecycleOperation.CLOSE_BY: {"position_id", "opposite_position_id"},
            LifecycleOperation.MODIFY_OCO: {"oco_group_id"},
            LifecycleOperation.CANCEL_OCO: {"oco_group_id"},
            LifecycleOperation.MODIFY_MANAGED_EXIT: {"managed_exit_plan_id"},
            LifecycleOperation.CLEAR_MANAGED_EXIT: {"managed_exit_plan_id"},
        }[self.operation]
        if present != expected:
            raise ValueError("lifecycle target IDs must match the declared operation")
        if (
            self.operation is LifecycleOperation.CLOSE_BY
            and self.position_id == self.opposite_position_id
        ):
            raise ValueError("close-by result position IDs must be different")
        return self


@final
class RejectedLifecycleResult(_UnsuccessfulLifecycleResult):
    kind: Literal["lifecycle_rejected_result"] = "lifecycle_rejected_result"
    status: Literal[LifecycleStatus.REJECTED] = LifecycleStatus.REJECTED


@final
class FailedLifecycleResult(_UnsuccessfulLifecycleResult):
    kind: Literal["lifecycle_failed_result"] = "lifecycle_failed_result"
    status: Literal[LifecycleStatus.FAILED] = LifecycleStatus.FAILED


type LifecycleResult = Annotated[
    OrderModifiedResult
    | OrderCancelledResult
    | PositionProtectedResult
    | FullPositionCloseResult
    | PartialPositionCloseResult
    | CloseByResult
    | OcoModifiedResult
    | OcoCancelledResult
    | ManagedExitModifiedResult
    | ManagedExitClearedResult
    | RejectedLifecycleResult
    | FailedLifecycleResult,
    Field(discriminator="kind"),
]

_LIFECYCLE_RESULT_ADAPTER: TypeAdapter[LifecycleResult] = TypeAdapter(LifecycleResult)


def validate_lifecycle_result(value: object) -> LifecycleResult:
    """Decode one untrusted lifecycle outcome through the closed discriminator."""
    return _LIFECYCLE_RESULT_ADAPTER.validate_python(value)
