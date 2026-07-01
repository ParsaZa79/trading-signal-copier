from __future__ import annotations

import pytest

from src import access_store, account_store, platform_store, runtime_data, security


def _isolate_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(security, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(security, "DEV_SECRET_PATH", tmp_path / ".dev_app_secret")
    monkeypatch.setattr(account_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(access_store, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.setattr(access_store, "LEGACY_USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(access_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(runtime_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(platform_store, "PLATFORM_PATH", tmp_path / "platform.json")


def _user(monkeypatch, tmp_path, email="owner@example.com"):
    _isolate_storage(monkeypatch, tmp_path)
    return security.create_user(email, "correct horse battery")


def test_provider_subscription_and_paper_execution_flow(monkeypatch, tmp_path):
    owner = _user(monkeypatch, tmp_path)
    follower = security.create_user("follower@example.com", "correct horse battery")

    provider = platform_store.create_provider(
        owner["id"],
        {
            "name": "Gold Desk",
            "source_type": "manual",
            "description": "Manual XAUUSD provider",
            "visibility": "public",
        },
    )
    policy = platform_store.upsert_risk_policy(
        follower["id"],
        {
            "paper_trading": True,
            "require_stop_loss": True,
            "allowed_symbols": ["XAUUSD"],
            "max_daily_loss": 100.0,
        },
    )
    subscription = platform_store.create_subscription(
        follower["id"],
        {
            "provider_id": provider["id"],
            "copy_mode": "fixed_lot",
            "fixed_lot": 0.03,
            "paper_trading": True,
        },
    )
    event = platform_store.create_trade_event(
        owner["id"],
        {
            "provider_id": provider["id"],
            "action": "open",
            "symbol": "xauusd",
            "side": "buy",
            "entry_price": 2350.5,
            "stop_loss": 2340.0,
            "take_profits": [2360.0, 2370.0],
            "source": "manual_dashboard",
        },
    )

    result = platform_store.process_trade_event(event["id"])

    assert policy["require_stop_loss"] is True
    assert subscription["status"] == "active"
    assert result["created"] == 1
    assert result["blocked"] == 0
    executions = platform_store.list_executions(follower["id"])
    assert len(executions) == 1
    execution = executions[0]
    assert execution["mode"] == "paper"
    assert execution["symbol"] == "XAUUSD"
    assert execution["side"] == "buy"
    assert execution["volume"] == 0.03
    assert execution["status"] == "accepted"

    # Idempotent: processing the same event twice must not duplicate follower execution.
    second = platform_store.process_trade_event(event["id"])
    assert second["created"] == 0
    assert len(platform_store.list_executions(follower["id"])) == 1


def test_risk_policy_blocks_missing_sl_and_disallowed_symbols(monkeypatch, tmp_path):
    owner = _user(monkeypatch, tmp_path)
    follower = security.create_user("follower@example.com", "correct horse battery")
    provider = platform_store.create_provider(
        owner["id"], {"name": "FX Desk", "source_type": "webhook"}
    )
    platform_store.upsert_risk_policy(
        follower["id"],
        {
            "paper_trading": True,
            "require_stop_loss": True,
            "allowed_symbols": ["EURUSD"],
        },
    )
    platform_store.create_subscription(
        follower["id"],
        {"provider_id": provider["id"], "copy_mode": "fixed_lot", "fixed_lot": 0.01},
    )

    missing_sl = platform_store.create_trade_event(
        owner["id"],
        {
            "provider_id": provider["id"],
            "action": "open",
            "symbol": "EURUSD",
            "side": "sell",
            "entry_price": 1.08,
            "source": "webhook",
        },
    )
    disallowed = platform_store.create_trade_event(
        owner["id"],
        {
            "provider_id": provider["id"],
            "action": "open",
            "symbol": "XAUUSD",
            "side": "buy",
            "entry_price": 2350.0,
            "stop_loss": 2340.0,
            "source": "webhook",
        },
    )

    missing_sl_result = platform_store.process_trade_event(missing_sl["id"])
    disallowed_result = platform_store.process_trade_event(disallowed["id"])

    assert missing_sl_result["created"] == 0
    assert missing_sl_result["blocked"] == 1
    assert missing_sl_result["results"][0]["reason"] == "stop_loss_required"
    assert disallowed_result["created"] == 0
    assert disallowed_result["blocked"] == 1
    assert disallowed_result["results"][0]["reason"] == "symbol_not_allowed"

    executions = platform_store.list_executions(follower["id"])
    assert len(executions) == 2
    assert {item["status"] for item in executions} == {"blocked"}


def test_stress_test_generates_events_and_summary(monkeypatch, tmp_path):
    owner = _user(monkeypatch, tmp_path)
    follower = security.create_user("follower@example.com", "correct horse battery")
    provider = platform_store.create_provider(
        owner["id"], {"name": "Stress Provider", "source_type": "manual"}
    )
    platform_store.upsert_risk_policy(
        follower["id"],
        {"paper_trading": True, "require_stop_loss": True, "allowed_symbols": ["XAUUSD"]},
    )
    platform_store.create_subscription(
        follower["id"],
        {"provider_id": provider["id"], "copy_mode": "fixed_lot", "fixed_lot": 0.02},
    )

    result = platform_store.run_stress_test(owner["id"], provider["id"], count=25)

    assert result["events"] == 25
    assert result["executions_created"] == 25
    assert result["blocked"] == 0
    assert result["duration_ms"] >= 0
    assert len(platform_store.list_executions(follower["id"])) == 25


def test_private_provider_cannot_be_subscribed_by_non_owner(monkeypatch, tmp_path):
    owner = _user(monkeypatch, tmp_path)
    follower = security.create_user("follower@example.com", "correct horse battery")
    provider = platform_store.create_provider(
        owner["id"],
        {"name": "Private Desk", "source_type": "manual", "visibility": "private"},
    )

    assert platform_store.list_providers(follower["id"]) == []
    with pytest.raises(PermissionError, match="Provider is private"):
        platform_store.create_subscription(
            follower["id"],
            {"provider_id": provider["id"], "copy_mode": "fixed_lot", "fixed_lot": 0.01},
        )


def test_subscriptions_remain_paper_only_even_if_live_requested(monkeypatch, tmp_path):
    owner = _user(monkeypatch, tmp_path)
    follower = security.create_user("follower@example.com", "correct horse battery")
    provider = platform_store.create_provider(
        owner["id"], {"name": "Paper Guard", "source_type": "manual"}
    )
    subscription = platform_store.create_subscription(
        follower["id"],
        {
            "provider_id": provider["id"],
            "copy_mode": "fixed_lot",
            "fixed_lot": 0.01,
            "paper_trading": False,
        },
    )
    event = platform_store.create_trade_event(
        owner["id"],
        {
            "provider_id": provider["id"],
            "action": "open",
            "symbol": "XAUUSD",
            "side": "buy",
            "entry_price": 2350.0,
            "stop_loss": 2340.0,
            "source": "manual_dashboard",
        },
    )

    result = platform_store.process_trade_event(event["id"])
    execution = platform_store.list_executions(follower["id"])[0]

    assert subscription["paper_trading"] is True
    assert result["created"] == 1
    assert execution["mode"] == "paper"


def test_external_id_deduplicates_replayed_trade_events(monkeypatch, tmp_path):
    owner = _user(monkeypatch, tmp_path)
    follower = security.create_user("follower@example.com", "correct horse battery")
    provider = platform_store.create_provider(
        owner["id"], {"name": "Webhook Desk", "source_type": "webhook"}
    )
    platform_store.create_subscription(
        follower["id"],
        {"provider_id": provider["id"], "copy_mode": "fixed_lot", "fixed_lot": 0.02},
    )
    payload = {
        "provider_id": provider["id"],
        "action": "open",
        "symbol": "XAUUSD",
        "side": "buy",
        "entry_price": 2350.0,
        "stop_loss": 2340.0,
        "source": "webhook",
        "external_id": "same-webhook-id",
    }

    first = platform_store.create_trade_event(owner["id"], payload)
    second = platform_store.create_trade_event(owner["id"], payload)
    first_result = platform_store.process_trade_event(first["id"])
    second_result = platform_store.process_trade_event(second["id"])

    assert second["id"] == first["id"]
    assert first_result["created"] == 1
    assert second_result["created"] == 0
    assert second_result["skipped"] == 1
    assert len(platform_store.list_executions(follower["id"])) == 1
