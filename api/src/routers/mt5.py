"""MT5 connection management router."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..account_store import get_active_account, load_account_config, save_account_config
from ..dependencies import connect_account_executor

router = APIRouter()


class MT5ConnectRequest(BaseModel):
    """Request to connect or reconnect the running API to MT5."""

    login: int | None = Field(default=None, gt=0)
    password: str | None = None
    server: str | None = None
    docker_host: str | None = None
    docker_port: int | None = Field(default=None, gt=0, le=65535)
    path: str | None = None

    @field_validator("server", "password", "docker_host", "path", mode="before")
    @classmethod
    def _strip_optional_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class MT5ConnectResponse(BaseModel):
    """Sanitized MT5 connection response."""

    success: bool
    connected: bool
    health: dict[str, Any]
    error: str | None = None


@router.post("/connect", response_model=MT5ConnectResponse)
async def connect_mt5(
    request: MT5ConnectRequest,
    account: dict = Depends(get_active_account),
) -> MT5ConnectResponse:
    """Connect the running API process to MT5 using dashboard-provided credentials."""
    updates = {
        key: value
        for key, value in {
            "MT5_LOGIN": str(request.login) if request.login is not None else None,
            "MT5_PASSWORD": request.password,
            "MT5_SERVER": request.server,
            "MT5_DOCKER_HOST": request.docker_host,
            "MT5_DOCKER_PORT": str(request.docker_port) if request.docker_port is not None else None,
            "MT5_PATH": request.path,
        }.items()
        if value is not None
    }
    if updates:
        save_account_config(account["id"], updates)

    config = load_account_config(account["id"], reveal_secrets=True)
    missing = [
        label
        for label, key in (
            ("login", "MT5_LOGIN"),
            ("password", "MT5_PASSWORD"),
            ("server", "MT5_SERVER"),
        )
        if not config.get(key)
    ]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing MT5 {', '.join(missing)}")

    result = connect_account_executor(account["id"], config)
    return MT5ConnectResponse(
        success=bool(result.get("success")),
        connected=bool(result.get("connected")),
        health=result.get("health", {}),
        error=result.get("error"),
    )
