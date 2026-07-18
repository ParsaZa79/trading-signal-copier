"""Shared runtime data paths for account configuration and legacy imports."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DATA_DIR = REPO_ROOT / ".runtime-data"
LEGACY_SIGNAL_APP_DIR = REPO_ROOT / "bot"
ENV_PATH = LEGACY_SIGNAL_APP_DIR / ".env"


def _resolve_data_dir() -> Path:
    """Resolve persistent data directory.

    Priority:
    1) TRADING_DATA_DIR env var
    2) /app/data when running in containerized deployments
    3) repo-local runtime directory for local development
    """
    configured = os.getenv("TRADING_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    if Path("/app").exists():
        return Path("/app/data")
    return LOCAL_DATA_DIR


DATA_DIR = _resolve_data_dir()
ACCOUNTS_DIR = DATA_DIR / "accounts"
CACHE_PATH = DATA_DIR / "bot_config_cache.json"
PRESETS_DIR = DATA_DIR / "presets"
LAST_PRESET_PATH = PRESETS_DIR / "_last_preset.json"

# Legacy locations retained only for an idempotent one-time config import.
LEGACY_CACHE_PATH = LEGACY_SIGNAL_APP_DIR / ".env.gui_cache.json"
LEGACY_PRESETS_DIR = LEGACY_SIGNAL_APP_DIR / ".presets"


def account_dir(account_id: str) -> Path:
    """Return the persistent directory for an account."""
    return ACCOUNTS_DIR / account_id


def account_config_path(account_id: str) -> Path:
    """Return the encrypted runtime config path for an account."""
    return account_dir(account_id) / "config.json"


def account_presets_dir(account_id: str) -> Path:
    """Return the presets directory for an account."""
    return account_dir(account_id) / "presets"


def account_last_preset_path(account_id: str) -> Path:
    """Return the last-used preset marker path for an account."""
    return account_presets_dir(account_id) / "_last_preset.json"


def account_prompts_path(account_id: str) -> Path:
    """Return the custom system prompts path for an account."""
    return account_dir(account_id) / "system_prompts.json"


def account_analysis_dir(account_id: str) -> Path:
    """Return the signal analysis directory for an account."""
    return account_dir(account_id) / "analysis"


def account_analysis_outcomes_path(account_id: str) -> Path:
    """Return the signal outcomes JSON path for an account."""
    return account_analysis_dir(account_id) / "signals_outcomes.json"


def _copy_file_if_missing(source: Path, target: Path) -> None:
    if not source.exists() or target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _migrate_legacy_presets() -> None:
    if not LEGACY_PRESETS_DIR.exists():
        return
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    for legacy_preset in LEGACY_PRESETS_DIR.glob("*.json"):
        target_path = PRESETS_DIR / legacy_preset.name
        if not target_path.exists():
            shutil.copy2(legacy_preset, target_path)


def bootstrap_runtime_data() -> None:
    """Ensure runtime directories exist and migrate legacy data once."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    _copy_file_if_missing(LEGACY_CACHE_PATH, CACHE_PATH)
    _migrate_legacy_presets()


bootstrap_runtime_data()
