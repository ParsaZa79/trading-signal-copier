from pathlib import Path

from src.services.copy_legacy_migration import _load_legacy_records
from src.services.copy_worker import calculate_risk_volume, evaluate_risk_limits


def test_risk_volume_uses_money_at_stop_and_rounds_down() -> None:
    result = calculate_risk_volume(
        balance=10_000,
        risk_pct=0.25,
        entry_price=2000,
        stop_loss=1995,
        value_per_price_unit_per_lot=10,
        volume_step=0.01,
    )

    assert result.blocked_reason is None
    assert result.volume == 0.5


def test_risk_volume_blocks_missing_or_invalid_stop_loss() -> None:
    missing = calculate_risk_volume(
        balance=10_000,
        risk_pct=0.25,
        entry_price=2000,
        stop_loss=None,
        value_per_price_unit_per_lot=10,
    )
    invalid = calculate_risk_volume(
        balance=10_000,
        risk_pct=0.25,
        entry_price=2000,
        stop_loss=2000,
        value_per_price_unit_per_lot=10,
    )

    assert missing.blocked_reason == "stop_loss_required"
    assert invalid.blocked_reason == "invalid_stop_loss"


def test_risk_volume_respects_broker_volume_limits() -> None:
    too_small = calculate_risk_volume(
        balance=100,
        risk_pct=0.25,
        entry_price=2000,
        stop_loss=1900,
        value_per_price_unit_per_lot=10,
        volume_min=0.01,
    )
    capped = calculate_risk_volume(
        balance=1_000_000,
        risk_pct=1,
        entry_price=100,
        stop_loss=99,
        value_per_price_unit_per_lot=1,
        volume_max=50,
    )

    assert too_small.blocked_reason == "trade_too_small_for_broker"
    assert capped.volume == 50


def test_legacy_json_reader_is_safe_and_non_mutating(tmp_path: Path) -> None:
    missing = _load_legacy_records(tmp_path / "missing.json")
    invalid_path = tmp_path / "platform.json"
    invalid_path.write_text("not json", encoding="utf-8")

    assert missing == {}
    assert _load_legacy_records(invalid_path) == {}


def test_daily_and_combined_open_risk_limits() -> None:
    daily = evaluate_risk_limits(
        balance=10_000,
        daily_copy_pnl=-200,
        current_open_risk_pct=0.5,
        next_trade_risk_pct=0.5,
        daily_loss_limit_pct=2,
        total_open_risk_pct=2.5,
    )
    combined = evaluate_risk_limits(
        balance=10_000,
        daily_copy_pnl=-50,
        current_open_risk_pct=2.25,
        next_trade_risk_pct=0.5,
        daily_loss_limit_pct=2,
        total_open_risk_pct=2.5,
    )

    assert daily == "daily_loss_limit_reached"
    assert combined == "combined_open_risk_limit_reached"
