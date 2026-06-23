import json

import pytest
from fastapi import HTTPException

from src import access_store, account_store, dependencies, runtime_data, security


def _isolate_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(security, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(security, "DEV_SECRET_PATH", tmp_path / ".dev_app_secret")
    monkeypatch.setattr(account_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(access_store, "ACCESS_PATH", tmp_path / "access.json")
    monkeypatch.setattr(access_store, "LEGACY_USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(access_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(runtime_data, "DATA_DIR", tmp_path)
    monkeypatch.setattr(runtime_data, "ACCOUNTS_DIR", tmp_path / "accounts")


def test_auth_token_round_trip(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    raw_user = security.get_user(user["id"])
    assert raw_user is not None

    token = security.create_token(user["id"])
    payload = security.decode_token(token)

    assert payload is not None
    assert payload["sub"] == user["id"]
    assert security.authenticate_credentials("owner@example.com", "correct horse battery")
    assert security.authenticate_credentials("owner@example.com", "wrong password") is None


def test_account_config_encrypts_and_masks_secrets(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    account = account_store.create_account(user["id"], "Primary Account")

    account_store.save_account_config(
        account["id"],
        {
            "MT5_LOGIN": "123456",
            "MT5_PASSWORD": "broker-password",
            "MT5_SERVER": "Broker-Real",
            "DEFAULT_LOT_SIZE": "0.01",
        },
    )

    raw = runtime_data.account_config_path(account["id"]).read_text(encoding="utf-8")
    assert "broker-password" not in raw
    assert json.loads(raw)["secrets"]["MT5_PASSWORD"].startswith("fernet:")

    revealed = account_store.load_account_config(account["id"], reveal_secrets=True)
    assert revealed["MT5_PASSWORD"] == "broker-password"

    sanitized, configured = account_store.sanitize_config(revealed)
    assert sanitized["MT5_PASSWORD"] == ""
    assert "MT5_PASSWORD" in configured


def test_blank_secret_save_preserves_existing_value(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    account = account_store.create_account(user["id"], "Primary Account")
    account_store.save_account_config(account["id"], {"MT5_PASSWORD": "first-password"})
    account_store.save_account_config(
        account["id"],
        {"MT5_PASSWORD": "", "MT5_SERVER": "Updated-Server"},
    )

    revealed = account_store.load_account_config(account["id"], reveal_secrets=True)
    assert revealed["MT5_PASSWORD"] == "first-password"
    assert revealed["MT5_SERVER"] == "Updated-Server"


def test_accounts_are_isolated(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    first = account_store.create_account(user["id"], "Primary Account")
    second = account_store.create_account(user["id"], "Second")

    account_store.save_account_config(first["id"], {"MT5_LOGIN": "111", "MT5_PASSWORD": "one"})
    account_store.save_account_config(second["id"], {"MT5_LOGIN": "222", "MT5_PASSWORD": "two"})

    first_config = account_store.load_account_config(first["id"], reveal_secrets=True)
    second_config = account_store.load_account_config(second["id"], reveal_secrets=True)

    assert first_config["MT5_LOGIN"] == "111"
    assert first_config["MT5_PASSWORD"] == "one"
    assert second_config["MT5_LOGIN"] == "222"
    assert second_config["MT5_PASSWORD"] == "two"


def test_clerk_owner_bootstrap_migrates_legacy_accounts(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")

    legacy_user = security.create_user("owner@example.com", "correct horse battery")
    legacy_account = account_store.create_account(legacy_user["id"], "Primary Account")

    member = access_store.resolve_clerk_member("user_clerk_owner", "owner@example.com")

    assert member["id"] == "user_clerk_owner"
    assert member["role"] == "owner"
    assert member["status"] == "active"
    assert member["active_account_id"] == legacy_account["id"]
    assert account_store.get_account(legacy_account["id"], "user_clerk_owner") is not None
    assert account_store.get_account(legacy_account["id"], legacy_user["id"]) is None


def test_accounts_are_not_created_until_requested(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")

    assert account_store.list_user_accounts(user["id"]) == []
    assert account_store.get_preferred_account(user) is None
    assert account_store.get_user_setup_status(user)["needs_account"] is True

    with pytest.raises(HTTPException) as exc_info:
        account_store.ensure_default_account(user)

    assert exc_info.value.status_code == 404


def test_account_setup_requires_broker_telegram_and_completion_marker(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)

    user = security.create_user("owner@example.com", "correct horse battery")
    account = account_store.create_account(user["id"], "Live Account")

    account_store.save_account_config(
        account["id"],
        {
            "MT5_LOGIN": "123456",
            "MT5_PASSWORD": "broker-password",
            "MT5_SERVER": "Broker-Real",
            "TELEGRAM_API_ID": "123456",
            "TELEGRAM_API_HASH": "telegram-hash",
            "TELEGRAM_CHANNEL": "signals",
        },
    )

    setup = account_store.get_user_setup_status(user)
    assert setup["setup_complete"] is False
    assert account_store.list_user_accounts(user["id"])[0]["setup_complete"] is False

    completed = account_store.mark_account_setup_complete(account["id"])
    refreshed = account_store.get_user_setup_status(user)

    assert completed["setup_complete"] is True
    assert refreshed["setup_complete"] is True
    assert account_store.list_user_accounts(user["id"])[0]["setup_complete"] is True


def test_invited_clerk_user_links_pending_access(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")

    pending = access_store.invite_member(
        email="trader@example.com",
        role="trader",
        invited_by="user_clerk_owner",
        invitation_id="inv_123",
        invitation_status="pending",
    )

    member = access_store.resolve_clerk_member("user_clerk_trader", "trader@example.com")
    members = access_store.list_members()

    assert pending["status"] == "pending"
    assert member["id"] == "user_clerk_trader"
    assert member["clerk_user_id"] == "user_clerk_trader"
    assert member["status"] == "active"
    assert member["invitation_status"] == "accepted"
    assert len(members) == 1


def test_access_store_keeps_at_least_one_active_owner(monkeypatch, tmp_path):
    _isolate_storage(monkeypatch, tmp_path)
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test")

    owner = access_store.resolve_clerk_member("user_clerk_owner", "owner@example.com")

    with pytest.raises(ValueError, match="At least one active owner"):
        access_store.update_member(owner["id"], status_value="disabled")

    with pytest.raises(ValueError, match="At least one active owner"):
        access_store.remove_member(owner["id"])


class _RuntimeExecutor:
    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self._mt5 = object() if connected else None
        self.disconnect_called = False

    def disconnect(self) -> None:
        self.disconnect_called = True
        self.connected = False
        self._mt5 = None


def test_mt5_executor_requires_account_to_own_runtime(monkeypatch):
    primary = _RuntimeExecutor()
    secondary = _RuntimeExecutor()
    monkeypatch.setattr(
        dependencies,
        "_mt5_executors",
        {"primary": primary, "secondary": secondary},
    )
    monkeypatch.setattr(dependencies, "_active_runtime_account_id", "primary")

    assert dependencies.get_mt5_executor({"id": "primary"}) is primary
    assert dependencies.is_account_runtime_active("primary", primary) is True
    assert dependencies.is_account_runtime_active("secondary", secondary) is False

    with pytest.raises(HTTPException) as exc_info:
        dependencies.get_mt5_executor({"id": "secondary"})

    assert exc_info.value.status_code == 503
    assert secondary.disconnect_called is True
