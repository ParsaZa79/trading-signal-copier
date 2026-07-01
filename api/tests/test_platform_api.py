from __future__ import annotations

from fastapi.testclient import TestClient

from src import access_store, account_store, platform_store, runtime_data, security
from src.main import app


def _isolate_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(security, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(security, "DEV_SECRET_PATH", tmp_path / ".dev_app_secret")
    monkeypatch.setattr(account_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(access_store, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.setattr(access_store, "LEGACY_USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(access_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(runtime_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(platform_store, "PLATFORM_PATH", tmp_path / "platform.json")


def _client(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)
    user = security.create_user("owner@example.com", "correct horse battery")
    token = security.create_token(user["id"])
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client, user


def test_platform_api_full_paper_copy_flow(monkeypatch, tmp_path):
    client, user = _client(monkeypatch, tmp_path)

    provider_response = client.post(
        "/api/platform/providers",
        json={"name": "Gold Desk", "source_type": "manual", "description": "Manual trades"},
    )
    assert provider_response.status_code == 200
    provider = provider_response.json()["provider"]

    risk_response = client.put(
        "/api/platform/risk-policy",
        json={
            "paper_trading": True,
            "require_stop_loss": True,
            "allowed_symbols": ["XAUUSD"],
            "max_daily_loss": 200,
            "max_open_trades": 50,
        },
    )
    assert risk_response.status_code == 200
    assert risk_response.json()["risk_policy"]["allowed_symbols"] == ["XAUUSD"]

    sub_response = client.post(
        "/api/platform/subscriptions",
        json={"provider_id": provider["id"], "copy_mode": "fixed_lot", "fixed_lot": 0.04},
    )
    assert sub_response.status_code == 200

    event_response = client.post(
        "/api/platform/trade-events",
        json={
            "provider_id": provider["id"],
            "action": "open",
            "symbol": "XAUUSD",
            "side": "buy",
            "entry_price": 2350,
            "stop_loss": 2340,
            "take_profits": [2360, 2370],
            "source": "manual_dashboard",
        },
    )
    assert event_response.status_code == 200
    event = event_response.json()["event"]

    process_response = client.post(f"/api/platform/trade-events/{event['id']}/process")
    assert process_response.status_code == 200
    assert process_response.json()["result"]["created"] == 1

    executions_response = client.get("/api/platform/executions")
    assert executions_response.status_code == 200
    executions = executions_response.json()["executions"]
    assert len(executions) == 1
    assert executions[0]["mode"] == "paper"
    assert executions[0]["volume"] == 0.04

    overview = client.get("/api/platform/overview").json()
    assert overview["metrics"]["provider_count"] == 1
    assert overview["metrics"]["subscription_count"] == 1
    assert overview["metrics"]["paper_execution_count"] == 1


def test_platform_stress_endpoint(monkeypatch, tmp_path):
    client, _user = _client(monkeypatch, tmp_path)
    provider = client.post(
        "/api/platform/providers",
        json={"name": "Stress Desk", "source_type": "manual"},
    ).json()["provider"]
    client.put(
        "/api/platform/risk-policy",
        json={"allowed_symbols": ["XAUUSD"], "max_open_trades": 100},
    )
    client.post(
        "/api/platform/subscriptions",
        json={"provider_id": provider["id"], "copy_mode": "fixed_lot", "fixed_lot": 0.01},
    )

    response = client.post(
        "/api/platform/stress-test",
        json={"provider_id": provider["id"], "count": 40},
    )

    assert response.status_code == 200
    result = response.json()["result"]
    assert result["events"] == 40
    assert result["executions_created"] == 40
    assert result["blocked"] == 0
