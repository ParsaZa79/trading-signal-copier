from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

import trading_strategy_sdk as sdk

NOW = datetime(2026, 7, 10, 12, 5, tzinfo=UTC)


def _successful_results() -> tuple[sdk.LifecycleResult, ...]:
    return (
        sdk.OrderModifiedResult(intent_id="modify", order_id="order_1", created_at=NOW),
        sdk.OrderCancelledResult(intent_id="cancel", order_id="order_1", created_at=NOW),
        sdk.PositionProtectedResult(intent_id="protect", position_id="position_1", created_at=NOW),
        sdk.FullPositionCloseResult(
            intent_id="close_full", position_id="position_1", created_at=NOW
        ),
        sdk.PartialPositionCloseResult(
            intent_id="close_partial",
            position_id="position_1",
            fraction=Decimal("0.5"),
            created_at=NOW,
        ),
        sdk.CloseByResult(
            intent_id="close_by",
            position_id="position_1",
            opposite_position_id="position_2",
            created_at=NOW,
        ),
        sdk.OcoModifiedResult(intent_id="modify_oco", oco_group_id="oco_1", created_at=NOW),
        sdk.OcoCancelledResult(intent_id="cancel_oco", oco_group_id="oco_1", created_at=NOW),
        sdk.ManagedExitModifiedResult(
            intent_id="modify_exit", managed_exit_plan_id="plan_1", created_at=NOW
        ),
        sdk.ManagedExitClearedResult(
            intent_id="clear_exit", managed_exit_plan_id="plan_1", created_at=NOW
        ),
    )


def test_every_mutating_lifecycle_operation_has_a_typed_discriminated_success_result() -> None:
    results = _successful_results()

    assert {result.operation for result in results} == set(sdk.LifecycleOperation)
    assert all(result.status is sdk.LifecycleStatus.SUCCEEDED for result in results)
    assert all(
        sdk.validate_lifecycle_result(result.model_dump(mode="json")) == result
        for result in results
    )
    assert "volume" not in "".join(result.model_dump_json() for result in results)


@pytest.mark.parametrize("status", [sdk.LifecycleStatus.REJECTED, sdk.LifecycleStatus.FAILED])
def test_unsuccessful_lifecycle_results_are_bounded_redacted_and_targeted(
    status: sdk.LifecycleStatus,
) -> None:
    model = (
        sdk.RejectedLifecycleResult
        if status is sdk.LifecycleStatus.REJECTED
        else sdk.FailedLifecycleResult
    )
    result = model(
        intent_id="modify",
        operation=sdk.LifecycleOperation.MODIFY_ORDER,
        status=status,
        order_id="order_1",
        created_at=NOW,
        reason="broker_rejected_request",
    )

    assert sdk.validate_lifecycle_result(result.model_dump(mode="json")) == result
    assert result.created_at.tzinfo is UTC

    with pytest.raises(ValidationError, match="target"):
        model(
            intent_id="modify",
            operation=sdk.LifecycleOperation.MODIFY_ORDER,
            status=status,
            created_at=NOW,
            reason="broker_rejected_request",
        )
    with pytest.raises(ValidationError):
        model(
            intent_id="modify",
            operation=sdk.LifecycleOperation.MODIFY_ORDER,
            status=status,
            order_id="order_1",
            created_at=NOW,
            reason="x" * 501,
        )
    with pytest.raises(ValidationError, match="redacted"):
        model(
            intent_id="modify",
            operation=sdk.LifecycleOperation.MODIFY_ORDER,
            status=status,
            order_id="order_1",
            created_at=NOW,
            reason="password=do-not-expose-this",
        )


def test_lifecycle_failure_target_ids_must_match_the_operation() -> None:
    with pytest.raises(ValidationError, match="operation"):
        sdk.FailedLifecycleResult(
            intent_id="cancel_oco",
            operation=sdk.LifecycleOperation.CANCEL_OCO,
            order_id="wrong_target_kind",
            created_at=NOW,
            reason="platform_failure",
        )
