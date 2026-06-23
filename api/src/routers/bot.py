"""Bot control router."""

import asyncio
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..account_store import get_active_account, load_account_config, save_account_config
from ..runtime_data import (
    BOT_DIR,
    account_pid_file,
    account_prompts_path,
    account_state_path,
)
from ..shared_telegram import shared_telegram_environment

router = APIRouter()
CurrentAccount = Annotated[dict[str, Any], Depends(get_active_account)]

# Per-account process state
BotStatus = Literal["stopped", "starting", "running", "stopping", "error"]
_bot_processes: dict[str, subprocess.Popen] = {}
_bot_statuses: dict[str, BotStatus] = {}
_bot_errors: dict[str, str | None] = {}
_started_at: dict[str, str | None] = {}

# Log manager will be injected from main.py
_log_manager = None


def set_log_manager(manager):
    """Set the log manager for streaming bot output."""
    global _log_manager
    _log_manager = manager


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


async def _load_env_for_bot(account_id: str) -> dict[str, str]:
    """Load runtime config from cache, with one-time fallback to legacy .env."""
    return load_account_config(account_id, reveal_secrets=True)


async def _check_bot_running(account_id: str) -> tuple[bool, int | None]:
    """Check if bot process is running.

    Returns (is_running, pid).
    """
    pid_file = account_pid_file(account_id)
    if not pid_file.exists():
        return False, None

    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return False, None

    # Check if process exists
    try:
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        return True, pid
    except (ProcessLookupError, PermissionError):
        # Process doesn't exist, clean up PID file
        try:
            pid_file.unlink()
        except OSError:
            pass
        return False, None


async def _stream_output(proc: subprocess.Popen, account_id: str):
    """Stream process output to log manager."""
    global _log_manager

    async def read_stream(stream, level: str):
        """Read from stream and send to log manager."""
        if stream is None:
            return

        loop = asyncio.get_event_loop()

        while True:
            try:
                line = await loop.run_in_executor(None, stream.readline)
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text and _log_manager:
                    await _log_manager.broadcast_log(text, level, account_id)
            except Exception:
                break

    if proc.stdout:
        asyncio.create_task(read_stream(proc.stdout, "info"))
    if proc.stderr:
        asyncio.create_task(read_stream(proc.stderr, "error"))


class StartBotRequest(BaseModel):
    """Request body for starting the bot."""

    prevent_sleep: bool = False
    write_env: bool = False
    config: dict[str, str] | None = None


class StopBotRequest(BaseModel):
    """Request body for stopping the bot."""

    pass


@router.get("/status")
async def get_bot_status(account: CurrentAccount):
    """Get current bot status."""
    account_id = account["id"]

    running, pid = await _check_bot_running(account_id)

    # Sync state if process died externally
    if not running and _bot_statuses.get(account_id) == "running":
        _bot_statuses[account_id] = "stopped"
        _started_at[account_id] = None

    return {
        "success": True,
        "account_id": account_id,
        "status": "running" if running else _bot_statuses.get(account_id, "stopped"),
        "pid": pid if running else None,
        "started_at": _started_at.get(account_id) if running else None,
        "error": _bot_errors.get(account_id),
    }


@router.post("/start")
async def start_bot(request: StartBotRequest, account: CurrentAccount):
    """Start the bot process."""
    account_id = account["id"]
    pid_file = account_pid_file(account_id)
    state_path = account_state_path(account_id)

    running, _ = await _check_bot_running(account_id)
    if running or _bot_statuses.get(account_id) in ("running", "starting"):
        raise HTTPException(status_code=400, detail="Bot is already running")

    _bot_statuses[account_id] = "starting"
    _bot_errors[account_id] = None

    try:
        # Persist config updates into the account-scoped encrypted config store.
        if request.write_env and request.config:
            save_account_config(account_id, request.config)

        # Load environment
        env_vars = await _load_env_for_bot(account_id)
        process_env = {
            **os.environ,
            **env_vars,
            **shared_telegram_environment(),
            "PYTHONUNBUFFERED": "1",
        }
        process_env["BOT_STATE_FILE"] = str(state_path)
        process_env["SYSTEM_PROMPTS_FILE"] = str(account_prompts_path(account_id))

        # Build command
        uv_path = shutil.which("uv")
        if uv_path:
            command = [uv_path, "run", "python", "-m", "tania_signal_copier.bot"]
        else:
            command = [sys.executable, "-m", "tania_signal_copier.bot"]

        # Wrap with caffeinate on macOS if requested
        if request.prevent_sleep and sys.platform == "darwin":
            caffeinate = shutil.which("caffeinate")
            if caffeinate:
                command = [caffeinate, "-dims", *command]

        # Spawn process
        proc = subprocess.Popen(
            command,
            cwd=str(BOT_DIR),
            env=process_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        _bot_processes[account_id] = proc
        _started_at[account_id] = datetime.now().isoformat()

        # Save PID
        if proc.pid:
            pid_file.parent.mkdir(parents=True, exist_ok=True)
            pid_file.write_text(str(proc.pid), encoding="utf-8")

        _bot_statuses[account_id] = "running"

        # Start streaming output
        await _stream_output(proc, account_id)

        # Monitor process in background
        async def monitor():
            loop = asyncio.get_event_loop()
            code = await loop.run_in_executor(None, proc.wait)

            _bot_statuses[account_id] = "stopped"
            if code != 0 and code is not None:
                _bot_errors[account_id] = f"Process exited with code {code}"

            _bot_processes.pop(account_id, None)
            _started_at[account_id] = None

            try:
                pid_file.unlink()
            except OSError:
                pass

        asyncio.create_task(monitor())

        return {
            "success": True,
            "status": "starting",
            "pid": proc.pid,
        }

    except Exception as e:
        _bot_status = "error"
        _bot_error = str(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/stop")
async def stop_bot(account: CurrentAccount):
    """Stop the bot process."""
    account_id = account["id"]
    pid_file = account_pid_file(account_id)

    running, pid = await _check_bot_running(account_id)

    if not running and _bot_statuses.get(account_id) != "running":
        raise HTTPException(status_code=400, detail="Bot is not running")

    _bot_statuses[account_id] = "stopping"

    # Try to stop by PID
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)

            # Give it 5 seconds to terminate gracefully
            async def force_kill():
                await asyncio.sleep(5)
                try:
                    os.kill(pid, 0)  # Check if still running
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass

            asyncio.create_task(force_kill())

        except (ProcessLookupError, PermissionError):
            pass

    # Also try process handle
    bot_process = _bot_processes.get(account_id)
    if bot_process:
        try:
            bot_process.terminate()

            async def force_kill_proc():
                await asyncio.sleep(5)
                proc = _bot_processes.get(account_id)
                if proc and proc.poll() is None:
                    proc.kill()

            asyncio.create_task(force_kill_proc())

        except Exception:
            pass

    # Clean up
    try:
        pid_file.unlink()
    except OSError:
        pass

    _bot_statuses[account_id] = "stopped"
    _bot_processes.pop(account_id, None)
    _started_at[account_id] = None

    return {"success": True, "status": "stopped"}


@router.get("/positions")
async def get_tracked_positions(account: CurrentAccount):
    """Get bot's tracked positions from state file."""
    import json

    state_path = account_state_path(account["id"])
    if not state_path.exists():
        return {
            "success": True,
            "account_id": account["id"],
            "positions": [],
            "total": 0,
            "open": 0,
            "closed": 0,
        }

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        positions_data = data.get("positions", {})
        positions: list[dict] = []

        for msg_id_str, dual_data in positions_data.items():
            msg_id = int(msg_id_str)

            if dual_data.get("scalp"):
                scalp = dual_data["scalp"]
                positions.append({
                    "msg_id": msg_id,
                    "mt5_ticket": scalp.get("mt5_ticket", 0),
                    "symbol": scalp.get("symbol", ""),
                    "role": "scalp",
                    "order_type": scalp.get("order_type", ""),
                    "entry_price": scalp.get("entry_price"),
                    "stop_loss": scalp.get("stop_loss"),
                    "lot_size": scalp.get("lot_size"),
                    "status": scalp.get("status", ""),
                    "opened_at": scalp.get("opened_at", ""),
                })

            if dual_data.get("runner"):
                runner = dual_data["runner"]
                positions.append({
                    "msg_id": msg_id,
                    "mt5_ticket": runner.get("mt5_ticket", 0),
                    "symbol": runner.get("symbol", ""),
                    "role": "runner",
                    "order_type": runner.get("order_type", ""),
                    "entry_price": runner.get("entry_price"),
                    "stop_loss": runner.get("stop_loss"),
                    "lot_size": runner.get("lot_size"),
                    "status": runner.get("status", ""),
                    "opened_at": runner.get("opened_at", ""),
                })

        # Sort by opened_at descending
        positions.sort(key=lambda x: x.get("opened_at", ""), reverse=True)

        return {
            "success": True,
            "account_id": account["id"],
            "positions": positions,
            "total": len(positions),
            "open": sum(1 for p in positions if p.get("status") == "open"),
            "closed": sum(1 for p in positions if p.get("status") == "closed"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/positions")
async def clear_tracked_positions(account: CurrentAccount):
    """Clear bot's tracked positions state file."""
    try:
        state_path = account_state_path(account["id"])
        if state_path.exists():
            state_path.unlink()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
