"""Server-owned Telegram configuration shared by all dashboard accounts."""

from __future__ import annotations

import json
import os
from typing import Any

from . import runtime_data

SHARED_TELEGRAM_FIELDS = ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_CHANNEL")
BLOCKED_ACCOUNT_TELEGRAM_FIELDS = (*SHARED_TELEGRAM_FIELDS, "TELEGRAM_SESSION_NAME")
SHARED_TELEGRAM_SESSION_FIELD = "TELEGRAM_SESSION"


def _parse_env_file() -> dict[str, str]:
    if not runtime_data.ENV_PATH.exists():
        return {}

    values: dict[str, str] = {}
    try:
        for line in runtime_data.ENV_PATH.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            value = raw_value.strip()
            if len(value) >= 2 and (
                (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
            ):
                value = value[1:-1]
            values[key.strip()] = value
    except OSError:
        return {}
    return values


def _parse_cache_file() -> dict[str, str]:
    if not runtime_data.CACHE_PATH.exists():
        return {}

    try:
        payload = json.loads(runtime_data.CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    raw_values = payload.get("values")
    values = raw_values if isinstance(raw_values, dict) else payload
    return {str(key): str(value) for key, value in values.items() if value is not None}


def _is_valid_api_id(value: str) -> bool:
    try:
        return int(value) > 0
    except ValueError:
        return False


def shared_telegram_config() -> dict[str, str]:
    """Load shared Telegram config from server-owned sources."""
    sources: list[dict[str, str]] = [
        {key: value for key in SHARED_TELEGRAM_FIELDS if (value := os.getenv(key, "").strip())},
        _parse_cache_file(),
        _parse_env_file(),
    ]

    config: dict[str, str] = {}
    for key in SHARED_TELEGRAM_FIELDS:
        for source in sources:
            value = source.get(key, "").strip()
            if value:
                config[key] = value
                break
    return config


def shared_telegram_missing_fields() -> list[str]:
    config = shared_telegram_config()
    missing: list[str] = []

    if not _is_valid_api_id(config.get("TELEGRAM_API_ID", "")):
        missing.append("TELEGRAM_API_ID")
    if not config.get("TELEGRAM_API_HASH"):
        missing.append("TELEGRAM_API_HASH")
    if not config.get("TELEGRAM_CHANNEL"):
        missing.append("TELEGRAM_CHANNEL")
    if not runtime_data.shared_telegram_session_path().exists():
        missing.append(SHARED_TELEGRAM_SESSION_FIELD)

    return missing


def shared_telegram_environment() -> dict[str, str]:
    config = shared_telegram_config()
    return {
        **config,
        "TELEGRAM_SESSION_NAME": str(runtime_data.shared_telegram_session_name()),
    }


def strip_account_telegram_values(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in values.items()
        if str(key).upper() not in BLOCKED_ACCOUNT_TELEGRAM_FIELDS
    }
