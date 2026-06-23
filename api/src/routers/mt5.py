"""MT5 connection management router."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..dependencies import get_mt5_executor

router = APIRouter()


class MT5ConnectRequest(BaseModel):
    """Request to connect or reconnect the running API to MT5."""

    login: int = Field(..., gt=0)
    password: str = Field(..., min_length=1)
    server: str = Field(..., min_length=1)
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
async def connect_mt5(request: MT5ConnectRequest) -> MT5ConnectResponse:
    """Connect the running API process to MT5 using dashboard-provided credentials."""
    try:
        executor = get_mt5_executor()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    result = executor.reconfigure(
        login=request.login,
        password=request.password,
        server=request.server,
        docker_host=request.docker_host,
        docker_port=request.docker_port,
        path=request.path,
    )
    return MT5ConnectResponse(
        success=bool(result.get("success")),
        connected=bool(result.get("connected")),
        health=result.get("health", {}),
        error=result.get("error"),
    )
