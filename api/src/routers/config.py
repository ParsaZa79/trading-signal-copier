"""Account-scoped MT5 runtime configuration."""

import json
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..account_store import (
    OBSOLETE_SIGNAL_KEYS,
    decode_config,
    encode_config,
    get_active_account,
    load_account_config,
    sanitize_config,
    save_account_config,
)
from ..runtime_data import ENV_PATH, account_last_preset_path, account_presets_dir

router = APIRouter()
CurrentAccount = Annotated[dict[str, Any], Depends(get_active_account)]


def _parse_env_value(raw: str) -> str:
    """Parse a value from .env file, removing quotes."""
    value = raw.strip()
    if len(value) >= 2 and (
        (value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")
    ):
        return value[1:-1]
    return value


def _format_env_value(value: str) -> str:
    """Format a value for .env file, adding quotes if needed."""
    if value == "":
        return ""
    if any(ch.isspace() for ch in value) or "#" in value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _read_env_file() -> dict[str, str]:
    """Read and parse .env file."""
    if not ENV_PATH.exists():
        return {}

    env: dict[str, str] = {}
    try:
        content = ENV_PATH.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            env[key.strip()] = _parse_env_value(raw_value)
    except Exception:
        pass

    return env


def _write_env_file(updates: dict[str, str]) -> None:
    """Write updates to .env file, preserving existing structure."""
    lines: list[str] = []
    if ENV_PATH.exists():
        try:
            lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
        except Exception:
            pass

    out_lines: list[str] = []
    seen: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out_lines.append(line)
            continue

        key = line.split("=", 1)[0].strip()
        if key in updates:
            out_lines.append(f"{key}={_format_env_value(updates[key])}")
            seen.add(key)
        else:
            out_lines.append(line)

    # Add new keys
    for key, value in updates.items():
        if key not in seen:
            out_lines.append(f"{key}={_format_env_value(value)}")

    content = "\n".join(out_lines).rstrip() + "\n"
    ENV_PATH.write_text(content, encoding="utf-8")


def _ensure_presets_dir(account_id: str) -> None:
    """Create presets directory if it doesn't exist."""
    account_presets_dir(account_id).mkdir(parents=True, exist_ok=True)


def _sanitize_preset_name(name: str) -> str:
    """Convert preset name to safe filename."""
    safe = "".join(c if c.isalnum() or c in " _-" else "" for c in name)
    return safe.strip().lower().replace(" ", "_").replace("-", "_")


class SaveConfigRequest(BaseModel):
    """Request body for saving config."""

    config: dict[str, str]
    write_env: bool = False


class SavePresetRequest(BaseModel):
    """Request body for saving a preset."""

    name: str
    values: dict[str, str]


# ============================================================
# Config Endpoints
# ============================================================


@router.get("")
@router.get("/")
async def get_config(account: CurrentAccount):
    """Get current account runtime configuration.

    Uses cached runtime values.
    If no cache exists yet, it imports values from legacy .env once.
    """
    try:
        values = load_account_config(account["id"], reveal_secrets=True)
        sanitized, configured_secrets = sanitize_config(values)
        return {
            "success": True,
            "account_id": account["id"],
            "config": sanitized,
            "configuredSecrets": configured_secrets,
            "secretFields": configured_secrets,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("")
@router.put("/")
async def save_config(request: SaveConfigRequest, account: CurrentAccount):
    """Save account runtime configuration.

    Always saves to cache. Optionally writes to .env file.
    """
    try:
        if not request.config or not isinstance(request.config, dict):
            raise HTTPException(status_code=400, detail="Invalid config")

        saved = save_account_config(account["id"], request.config)

        # Shared .env writes are intentionally disabled under multi-account mode.
        # Account runtimes receive account-scoped values when they start.
        _ = request.write_env

        _, configured_secrets = sanitize_config(saved)
        return {
            "success": True,
            "account_id": account["id"],
            "configuredSecrets": configured_secrets,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ============================================================
# Preset Endpoints
# ============================================================


@router.get("/presets")
async def list_presets(account: CurrentAccount):
    """List all saved presets."""
    try:
        presets_dir = account_presets_dir(account["id"])
        last_preset_path = account_last_preset_path(account["id"])
        _ensure_presets_dir(account["id"])

        presets: list[dict] = []
        for path in presets_dir.glob("*.json"):
            if path.name == "_last_preset.json":
                continue

            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                presets.append({
                    "name": data.get("name", path.stem),
                    "created_at": data.get("created_at", ""),
                    "modified_at": data.get("modified_at", ""),
                })
            except Exception:
                continue

        presets.sort(key=lambda x: x["name"].lower())

        # Get last used preset
        last_preset: str | None = None
        if last_preset_path.exists():
            try:
                data = json.loads(last_preset_path.read_text(encoding="utf-8"))
                last_preset = data.get("name")
            except Exception:
                pass

        return {"success": True, "presets": presets, "lastPreset": last_preset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/presets/{name}")
async def get_preset(name: str, account: CurrentAccount):
    """Get a specific preset by name."""
    try:
        presets_dir = account_presets_dir(account["id"])
        last_preset_path = account_last_preset_path(account["id"])
        _ensure_presets_dir(account["id"])

        filename = _sanitize_preset_name(name) + ".json"
        preset_path = presets_dir / filename

        if not preset_path.exists():
            raise HTTPException(status_code=404, detail="Preset not found")

        data = json.loads(preset_path.read_text(encoding="utf-8"))
        values_payload = data.get("values", {})
        values = (
            {
                key: value
                for key, value in decode_config(values_payload, reveal_secrets=True).items()
                if key not in OBSOLETE_SIGNAL_KEYS
            }
            if isinstance(values_payload, dict)
            else {}
        )
        sanitized, configured_secrets = sanitize_config(values)

        # Update last preset
        last_preset_path.write_text(
            json.dumps({"name": data.get("name", name)}),
            encoding="utf-8",
        )

        return {
            "success": True,
            "preset": {
                "name": data.get("name", name),
                "created_at": data.get("created_at"),
                "modified_at": data.get("modified_at"),
                "values": sanitized,
                "configuredSecrets": configured_secrets,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/presets")
async def save_preset(request: SavePresetRequest, account: CurrentAccount):
    """Save a preset (create or update)."""
    try:
        if not request.name or not isinstance(request.name, str):
            raise HTTPException(status_code=400, detail="Invalid preset name")

        presets_dir = account_presets_dir(account["id"])
        last_preset_path = account_last_preset_path(account["id"])
        _ensure_presets_dir(account["id"])

        filename = _sanitize_preset_name(request.name) + ".json"
        preset_path = presets_dir / filename
        now = datetime.now().isoformat()

        # Preserve created_at if updating
        created_at = now
        existing: dict = {}
        if preset_path.exists():
            try:
                existing = json.loads(preset_path.read_text(encoding="utf-8"))
                created_at = existing.get("created_at", now)
            except Exception:
                pass

        existing_values_payload = existing.get("values", {}) if isinstance(existing, dict) else {}
        existing_values = (
            {
                key: value
                for key, value in decode_config(
                    existing_values_payload,
                    reveal_secrets=True,
                ).items()
                if key not in OBSOLETE_SIGNAL_KEYS
            }
            if isinstance(existing_values_payload, dict)
            else {}
        )
        preset_values = {
            key: value
            for key, value in (request.values or {}).items()
            if key not in OBSOLETE_SIGNAL_KEYS
        }

        data = {
            "name": request.name,
            "created_at": created_at,
            "modified_at": now,
            "values": encode_config(
                preset_values,
                existing_payload=encode_config(existing_values, preserve_blank_secrets=False),
            ),
        }

        preset_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Update last preset
        last_preset_path.write_text(json.dumps({"name": request.name}), encoding="utf-8")

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/presets/{name}")
async def delete_preset(name: str, account: CurrentAccount):
    """Delete a preset by name."""
    try:
        presets_dir = account_presets_dir(account["id"])
        last_preset_path = account_last_preset_path(account["id"])
        _ensure_presets_dir(account["id"])

        filename = _sanitize_preset_name(name) + ".json"
        preset_path = presets_dir / filename

        if not preset_path.exists():
            raise HTTPException(status_code=404, detail="Preset not found")

        preset_path.unlink()

        # Clear last preset if it matches
        if last_preset_path.exists():
            try:
                data = json.loads(last_preset_path.read_text(encoding="utf-8"))
                if data.get("name") == name:
                    last_preset_path.unlink()
            except Exception:
                pass

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
