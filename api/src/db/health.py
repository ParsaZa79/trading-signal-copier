"""Non-invasive PostgreSQL health checks."""

import asyncio
from time import perf_counter
from typing import Literal, NotRequired, TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class DatabaseHealth(TypedDict):
    """Stable, secret-free result returned by the readiness probe."""

    status: Literal["healthy", "unhealthy"]
    latency_ms: float
    error: NotRequired[Literal["connection_failed", "timeout"]]


async def _ping(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def check_database_health(
    engine: AsyncEngine,
    *,
    timeout_seconds: float = 2.0,
) -> DatabaseHealth:
    """Return database readiness without exposing connection details."""
    started_at = perf_counter()
    try:
        await asyncio.wait_for(_ping(engine), timeout=timeout_seconds)
    except TimeoutError:
        return {
            "status": "unhealthy",
            "latency_ms": round((perf_counter() - started_at) * 1_000, 2),
            "error": "timeout",
        }
    except Exception:
        return {
            "status": "unhealthy",
            "latency_ms": round((perf_counter() - started_at) * 1_000, 2),
            "error": "connection_failed",
        }
    return {
        "status": "healthy",
        "latency_ms": round((perf_counter() - started_at) * 1_000, 2),
    }
