from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import access_store, account_store, runtime_data, security
from src.routers import access as access_router
from src.session_payload import build_session_payload


def test_owner_session_payload_preserves_role_and_existing_account(monkeypatch, tmp_path):
    monkeypatch.setattr(security, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(security, "DEV_SECRET_PATH", tmp_path / ".dev_app_secret")
    monkeypatch.setattr(account_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(access_store, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.setattr(access_store, "LEGACY_USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(access_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(runtime_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(runtime_data, "ACCOUNTS_DIR", tmp_path / "accounts")

    owner = security.create_user("owner@example.com", "correct horse battery")
    account = account_store.create_account(owner["id"], "Primary Account")

    response = build_session_payload(owner)

    assert response["user"]["id"] == owner["id"]
    assert response["user"]["role"] == "owner"
    assert response["active_account_id"] == account["id"]
    assert [item["id"] for item in response["accounts"]] == [account["id"]]


def test_session_endpoint_provisions_trader_without_an_account(monkeypatch, tmp_path):
    monkeypatch.setenv("DASHBOARD_PROXY_SECRET", "shared-secret")
    monkeypatch.setenv("ACCESS_BOOTSTRAP_EMAILS", "owner@example.com")
    monkeypatch.setattr(account_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(access_store, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.setattr(access_store, "LEGACY_USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(access_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(runtime_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(runtime_data, "ACCOUNTS_DIR", tmp_path / "accounts")

    app = FastAPI()
    app.include_router(access_router.router, prefix="/api/access")
    with TestClient(app) as client:
        response = client.post(
            "/api/access/session",
            headers={
                "x-dashboard-proxy-auth": "shared-secret",
                "x-workos-user-id": "user_trader",
                "x-workos-user-email": "trader@example.com",
                "x-workos-session-id": "session_123",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["role"] == "trader"
    assert payload["accounts"] == []
    assert payload["active_account_id"] is None
    assert payload["setup_complete"] is False
    assert access_store.resolve_workos_member_by_id("user_trader")["role"] == "trader"
