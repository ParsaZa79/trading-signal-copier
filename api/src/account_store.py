"""User-owned account storage and account-scoped runtime paths."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, cast

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status

from .runtime_data import (
    CACHE_PATH,
    DATA_DIR,
    ENV_PATH,
    LAST_PRESET_PATH,
    PRESETS_DIR,
    account_config_path,
    account_dir,
    account_last_preset_path,
    account_presets_dir,
)
from .security import (
    app_secret_bytes,
    get_current_user,
    get_requested_account_id,
    set_active_account_id,
)

ACCOUNTS_PATH = DATA_DIR / "accounts.json"
MASKED_SECRET = "__configured_secret__"
SETUP_COMPLETED_KEY = "SETUP_COMPLETED_AT"
BROKER_SETUP_FIELDS = ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")

SECRET_FIELD_NAMES = {
    "MT5_PASSWORD",
    "GROQ_API_KEY",
    "CEREBRAS_API_KEY",
    "OPENAI_API_KEY",
}
SECRET_KEYWORDS = ("PASSWORD", "SECRET", "TOKEN", "API_KEY", "PRIVATE_KEY")
OBSOLETE_SIGNAL_KEYS = {
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_CHANNEL",
    "TELEGRAM_SESSION_NAME",
}


def _without_obsolete_signal_ingestion(values: dict[str, Any]) -> dict[str, Any]:
    """Drop legacy Telegram settings while reading or updating an account."""
    return {key: value for key, value in values.items() if key not in OBSOLETE_SIGNAL_KEYS}


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
    return _without_obsolete_signal_ingestion(decode_config(payload, reveal_secrets=reveal_secrets))


def save_account_config(account_id: str, values: dict[str, Any]) -> dict[str, str]:
    path = account_config_path(account_id)
    existing = _read_json(path, {})
    merged = _without_obsolete_signal_ingestion(decode_config(existing, reveal_secrets=True))

    for key, raw_value in _without_obsolete_signal_ingestion(values).items():
        value = "" if raw_value is None else str(raw_value)
        if is_secret_key(str(key)) and value in {"", MASKED_SECRET}:
            continue
        merged[str(key)] = value

    payload = encode_config(merged, preserve_blank_secrets=False)
    _write_json(path, payload)
    return decode_config(payload, reveal_secrets=True)


def _is_account_setup_complete(account_id: str) -> bool:
    values = load_account_config(account_id, reveal_secrets=True)
    return (
        bool(values.get(SETUP_COMPLETED_KEY))
        and all(values.get(key) for key in BROKER_SETUP_FIELDS)
    )


def _sanitize_account(account: dict[str, Any], *, include_setup: bool = True) -> dict[str, Any]:
    sanitized = {
        "id": account["id"],
        "name": account.get("name") or "Trading Account",
        "user_id": account["user_id"],
        "created_at": account.get("created_at"),
        "updated_at": account.get("updated_at"),
    }
    if include_setup:
        sanitized["setup_complete"] = _is_account_setup_complete(account["id"])
    return sanitized


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


def get_preferred_account(user: dict[str, Any]) -> dict[str, Any] | None:
    accounts = list_user_accounts(user["id"])
    if not accounts:
        return None

    active = user.get("active_account_id")
    if active and (account := get_account(active, user["id"])):
        return account

    first_complete = next((account for account in accounts if account.get("setup_complete")), None)
    selected = first_complete or accounts[0]
    set_active_account_id(user["id"], selected["id"])
    return selected


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


def create_account(
    user_id: str,
    name: str | None = None,
    *,
    migrate_legacy: bool = False,
) -> dict[str, Any]:
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
    account = get_preferred_account(user)
    if account:
        return account
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Account setup required",
    )


def account_setup_status(account: dict[str, Any]) -> dict[str, Any]:
    values = load_account_config(account["id"], reveal_secrets=True)
    broker_missing = [key for key in BROKER_SETUP_FIELDS if not values.get(key)]
    missing_fields = [*broker_missing]
    if not values.get(SETUP_COMPLETED_KEY):
        missing_fields.append(SETUP_COMPLETED_KEY)
    return {
        "account": _sanitize_account(account),
        "setup_complete": not missing_fields,
        "broker_configured": not broker_missing,
        "missing_fields": missing_fields,
    }


def get_user_setup_status(user: dict[str, Any]) -> dict[str, Any]:
    accounts = list_user_accounts(user["id"])
    active = get_preferred_account(user)
    account_statuses = [account_setup_status(account) for account in accounts]
    active_status = (
        next(
            (item for item in account_statuses if item["account"]["id"] == active["id"]),
            None,
        )
        if active
        else None
    )
    return {
        "setup_complete": bool(active_status and active_status["setup_complete"]),
        "needs_account": not accounts,
        "active_account_id": active["id"] if active else None,
        "accounts": accounts,
        "account_statuses": account_statuses,
    }


def mark_account_setup_complete(account_id: str) -> dict[str, Any]:
    account = get_account(account_id)
    if not account:
        raise ValueError("Account not found")

    values = load_account_config(account_id, reveal_secrets=True)
    missing = [key for key in BROKER_SETUP_FIELDS if not values.get(key)]
    if missing:
        raise ValueError(f"Missing broker setup fields: {', '.join(missing)}")

    save_account_config(account_id, {SETUP_COMPLETED_KEY: _utc_now()})
    return account_setup_status(account)


async def get_active_account(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
    requested_account_id: Annotated[str | None, Depends(get_requested_account_id)],
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
    return get_preferred_account(user)


def set_user_active_account(user_id: str, account_id: str) -> dict[str, Any]:
    account = get_account(account_id, user_id)
    if not account:
        raise ValueError("Account not found")
    set_active_account_id(user_id, account_id)
    return account
