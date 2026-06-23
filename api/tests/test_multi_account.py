import json

from src import account_store, runtime_data, security


def _isolate_storage(monkeypatch, tmp_path):
    monkeypatch.setattr(security, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(security, "DEV_SECRET_PATH", tmp_path / ".dev_app_secret")
    monkeypatch.setattr(account_store, "ACCOUNTS_PATH", tmp_path / "accounts.json")
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
    account = account_store.ensure_default_account(user)

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
    account = account_store.ensure_default_account(user)
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
    first = account_store.ensure_default_account(user)
    second = account_store.create_account(user["id"], "Second")

    account_store.save_account_config(first["id"], {"MT5_LOGIN": "111", "MT5_PASSWORD": "one"})
    account_store.save_account_config(second["id"], {"MT5_LOGIN": "222", "MT5_PASSWORD": "two"})

    first_config = account_store.load_account_config(first["id"], reveal_secrets=True)
    second_config = account_store.load_account_config(second["id"], reveal_secrets=True)

    assert first_config["MT5_LOGIN"] == "111"
    assert first_config["MT5_PASSWORD"] == "one"
    assert second_config["MT5_LOGIN"] == "222"
    assert second_config["MT5_PASSWORD"] == "two"
