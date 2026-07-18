"""API Configuration."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .runtime_data import CACHE_PATH

# Load .env file
load_dotenv()


def _load_runtime_cache() -> dict[str, str]:
    """Load dashboard-saved runtime config values."""
    if not CACHE_PATH.exists():
        return {}

    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


_RUNTIME_CONFIG = _load_runtime_cache()


def _config_value(name: str, default: str = "") -> str:
    """Read dashboard runtime config first, then process env."""
    return _RUNTIME_CONFIG.get(name) or os.getenv(name, default)


def _config_int(name: str, default: int) -> int:
    raw = _config_value(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _config_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class FeatureFlags:
    """Dark-launch controls for Strategy Lab capabilities."""

    strategy_lab_enabled: bool = field(
        default_factory=lambda: _config_bool("STRATEGY_LAB_ENABLED")
    )
    open_signup_enabled: bool = field(
        default_factory=lambda: _config_bool("OPEN_SIGNUP_ENABLED")
    )
    codex_builder_enabled: bool = field(
        default_factory=lambda: _config_bool("CODEX_BUILDER_ENABLED")
    )
    paper_live_enabled: bool = field(
        default_factory=lambda: _config_bool("PAPER_LIVE_ENABLED")
    )
    public_strategy_publishing_enabled: bool = field(
        default_factory=lambda: _config_bool("PUBLIC_STRATEGY_PUBLISHING_ENABLED")
    )


@dataclass
class MT5Config:
    """MT5 connection configuration."""

    login: int = field(default_factory=lambda: _config_int("MT5_LOGIN", 0))
    password: str = field(default_factory=lambda: _config_value("MT5_PASSWORD"))
    server: str = field(default_factory=lambda: _config_value("MT5_SERVER"))
    docker_host: str = field(default_factory=lambda: _config_value("MT5_DOCKER_HOST", "localhost"))
    docker_port: int = field(default_factory=lambda: _config_int("MT5_DOCKER_PORT", 8001))
    path: str | None = field(default_factory=lambda: _config_value("MT5_PATH") or None)


@dataclass
class APIConfig:
    """API server configuration."""

    host: str = field(default_factory=lambda: os.getenv("API_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(os.getenv("API_PORT", "8000")))
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
    )
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")


@dataclass
class DatabaseConfig:
    """Database configuration."""

    url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{Path(__file__).parent.parent / 'trade_history.db'}",
        )
    )


@dataclass
class Config:
    """Main configuration combining all configs."""

    mt5: MT5Config = field(default_factory=MT5Config)
    api: APIConfig = field(default_factory=APIConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)

# Global config instance
config = Config()
