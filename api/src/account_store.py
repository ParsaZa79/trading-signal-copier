"""User-owned account storage and account-scoped runtime paths."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status

from .runtime_data import (
    CACHE_PATH,
    DATA_DIR,
    ENV_PATH,
    LAST_PRESET_PATH,
    LEGACY_SESSION_PATHS,
    PID_FILE,
    PRESETS_DIR,
    STATE_PATH,
    account_config_path,
    account_dir,
    account_last_preset_path,
    account_pid_file,
    account_presets_dir,
    account_state_path,
    account_telegram_session_path,
)
from .security import (
    app_secret_bytes,
    get_current_user,
    get_requested_account_id,
    set_active_account_id,
)

ACCOUNTS_PATH = DATA_DIR / "accounts.json"
MASKED_SECRET = "__configured_secret__"

SECRET_FIELD_NAMES = {
    "MT5_PASSWORD",
    "TELEGRAM_API_HASH",
    "GROQ_API_KEY",
    "CEREBRAS_API_KEY",
    "OPENAI_API_KEY",
}
SECRET_KEYWORDS = ("PASSWORD", "SECRET", "TOKEN", "API_KEY", "PRIVATE_KEY")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return data if isinstance(data, dict) else default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _load_accounts_store() -> dict[str, Any]:
    store = _read_json(ACCOUNTS_PATH, {"accounts": {}})
    if not isinstance(store.get("accounts"), dict):
        store["accounts"] = {}
    return store


def _save_accounts_store(store: dict[str, Any]) -> None:
    _write_json(ACCOUNTS_PATH, store)


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(app_secret_bytes()).digest())
    return Fernet(key)


def is_secret_key(key: str) -> bool:
    normalized = key.upper()
    return normalized in SECRET_FIELD_NAMES or any(word in normalized for word in SECRET_KEYWORDS)


def _encrypt(value: str) -> str:
    return "fernet:" + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(value: str) -> str:
    if not value.startswith("fernet:"):
        return value
    try:
        return _fernet().decrypt(value.removeprefix("fernet:").encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""


def encode_config(
    values: dict[str, Any],
    *,
    existing_payload: dict[str, Any] | None = None,
    preserve_blank_secrets: bool = True,
) -> dict[str, Any]:
    """Encode config with secret values encrypted and blank secrets preserved."""
    merged = decode_config(existing_payload or {}, reveal_secrets=True)

    for key, raw_value in values.items():
        value = "" if raw_value is None else str(raw_value)
        if is_secret_key(key) and preserve_blank_secrets and value in {"", MASKED_SECRET}:
            continue
        merged[str(key)] = value

    public_values: dict[str, str] = {}
    secrets_payload: dict[str, str] = {}

    for key, value in merged.items():
        if is_secret_key(key):
            if value:
                secrets_payload[key] = _encrypt(value)
        else:
            public_values[key] = value

    return {
        "version": 1,
        "values": public_values,
        "secrets": secrets_payload,
        "updated_at": _utc_now(),
    }


def decode_config(payload: dict[str, Any], *, reveal_secrets: bool) -> dict[str, str]:
    """Decode a config payload, including legacy plaintext dictionaries."""
    if "values" not in payload and "secrets" not in payload:
        return {str(key): str(value) for key, value in payload.items() if value is not None}

    raw_values = payload.get("values")
    raw_secrets = payload.get("secrets")
    values = cast(dict[Any, Any], raw_values) if isinstance(raw_values, dict) else {}
    secrets_payload = cast(dict[Any, Any], raw_secrets) if isinstance(raw_secrets, dict) else {}

    result = {str(key): str(value) for key, value in values.items() if value is not None}
    for key, value in secrets_payload.items():
        clean_key = str(key)
        decrypted = _decrypt(str(value))
        if reveal_secrets:
            result[clean_key] = decrypted
        elif decrypted:
            result[clean_key] = ""
    return result


def sanitize_config(values: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    configured: list[str] = []
    sanitized: dict[str, str] = {}
    for key, value in values.items():
        if is_secret_key(key):
            sanitized[key] = ""
            if value:
                configured.append(key)
        else:
            sanitized[key] = value
    return sanitized, sorted(configured)


def _read_env_file() -> dict[str, str]:
    if not ENV_PATH.exists():
        return {}
    env: dict[str, str] = {}
    try:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            value = raw_value.strip()
            if len(value) >= 2 and (
                (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
            ):
                value = value[1:-1]
            env[key.strip()] = value
    except Exception:
        return {}
    return env


def load_account_config(account_id: str, *, reveal_secrets: bool) -> dict[str, str]:
    path = account_config_path(account_id)
    payload = _read_json(path, {})
    return decode_config(payload, reveal_secrets=reveal_secrets)


def save_account_config(account_id: str, values: dict[str, Any]) -> dict[str, str]:
    path = account_config_path(account_id)
    existing = _read_json(path, {})
    payload = encode_config(values, existing_payload=existing, preserve_blank_secrets=True)
    _write_json(path, payload)
    return decode_config(payload, reveal_secrets=True)


def _sanitize_account(account: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": account["id"],
        "name": account.get("name") or "Trading Account",
        "user_id": account["user_id"],
        "created_at": account.get("created_at"),
        "updated_at": account.get("updated_at"),
    }


def list_user_accounts(user_id: str) -> list[dict[str, Any]]:
    accounts = [
        _sanitize_account(account)
        for account in _load_accounts_store()["accounts"].values()
        if isinstance(account, dict) and account.get("user_id") == user_id
    ]
    return sorted(accounts, key=lambda item: item.get("created_at") or "")


def get_account(account_id: str, user_id: str | None = None) -> dict[str, Any] | None:
    account = _load_accounts_store()["accounts"].get(account_id)
    if not isinstance(account, dict):
        return None
    if user_id is not None and account.get("user_id") != user_id:
        return None
    return _sanitize_account(account)


def _copy_file_if_missing(source: Path, target: Path) -> None:
    if not source.exists() or target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _migrate_legacy_runtime(account_id: str) -> None:
    """Move the old single-account runtime files into the first account."""
    account_dir(account_id).mkdir(parents=True, exist_ok=True)

    legacy_config = {}
    if CACHE_PATH.exists():
        legacy_config = _read_json(CACHE_PATH, {})
    if not legacy_config:
        legacy_config = _read_env_file()
    if legacy_config and not account_config_path(account_id).exists():
        save_account_config(account_id, legacy_config)

    _copy_file_if_missing(STATE_PATH, account_state_path(account_id))
    _copy_file_if_missing(PID_FILE, account_pid_file(account_id))

    for legacy_session in LEGACY_SESSION_PATHS:
        _copy_file_if_missing(legacy_session, account_telegram_session_path(account_id))

    if PRESETS_DIR.exists():
        target_presets = account_presets_dir(account_id)
        target_presets.mkdir(parents=True, exist_ok=True)
        for preset in PRESETS_DIR.glob("*.json"):
            target = target_presets / preset.name
            if target.exists():
                continue
            data = _read_json(preset, {})
            if isinstance(data.get("values"), dict):
                data["values"] = encode_config(data["values"])
                _write_json(target, data)
            elif data:
                _write_json(target, data)
        _copy_file_if_missing(LAST_PRESET_PATH, account_last_preset_path(account_id))


def create_account(user_id: str, name: str | None = None, *, migrate_legacy: bool = False) -> dict[str, Any]:
    store = _load_accounts_store()
    account_id = secrets.token_urlsafe(10)
    now = _utc_now()
    account = {
        "id": account_id,
        "user_id": user_id,
        "name": (name or "Trading Account").strip() or "Trading Account",
        "created_at": now,
        "updated_at": now,
    }
    store["accounts"][account_id] = account
    _save_accounts_store(store)

    account_dir(account_id).mkdir(parents=True, exist_ok=True)
    account_presets_dir(account_id).mkdir(parents=True, exist_ok=True)
    if migrate_legacy:
        _migrate_legacy_runtime(account_id)
    else:
        save_account_config(account_id, {})

    existing_accounts = list_user_accounts(user_id)
    if len(existing_accounts) == 1:
        set_active_account_id(user_id, account_id)
    return _sanitize_account(account)


def ensure_default_account(user: dict[str, Any]) -> dict[str, Any]:
    accounts = list_user_accounts(user["id"])
    if accounts:
        active = user.get("active_account_id")
        if active and (account := get_account(active, user["id"])):
            return account
        set_active_account_id(user["id"], accounts[0]["id"])
        return accounts[0]

    is_first_account = not bool(_load_accounts_store()["accounts"])
    return create_account(user["id"], "Primary Account", migrate_legacy=is_first_account)


async def get_active_account(
    current_user: dict[str, Any] = Depends(get_current_user),
    requested_account_id: str | None = Depends(get_requested_account_id),
) -> dict[str, Any]:
    if requested_account_id:
        account = get_account(requested_account_id, current_user["id"])
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found",
            )
        return account
    return ensure_default_account(current_user)


def get_websocket_account(user: dict[str, Any], account_id: str | None) -> dict[str, Any] | None:
    if account_id:
        return get_account(account_id, user["id"])
    return ensure_default_account(user)


def set_user_active_account(user_id: str, account_id: str) -> dict[str, Any]:
    account = get_account(account_id, user_id)
    if not account:
        raise ValueError("Account not found")
    set_active_account_id(user_id, account_id)
    return account
