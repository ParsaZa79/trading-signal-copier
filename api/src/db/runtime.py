"""Optional application PostgreSQL runtime used by database-backed features."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.db.session import (
    create_database_engine,
    create_session_factory,
    dispose_database_engine,
    session_scope,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _postgres_url() -> str | None:
    value = os.getenv("DATABASE_URL", "").strip()
    return value if value.startswith(("postgresql://", "postgresql+asyncpg://")) else None


async def start_database_runtime() -> bool:
    """Initialize the shared pool when a PostgreSQL URL is configured."""
    global _engine, _session_factory
    if _session_factory is not None:
        return True
    database_url = _postgres_url()
    if not database_url:
        return False
    _engine = create_database_engine(database_url)
    _session_factory = create_session_factory(_engine)
    return True


async def stop_database_runtime() -> None:
    """Dispose the optional database pool."""
    global _engine, _session_factory
    engine = _engine
    _engine = None
    _session_factory = None
    if engine is not None:
        await dispose_database_engine(engine)


def database_runtime_available() -> bool:
    return _session_factory is not None


def database_session_factory() -> async_sessionmaker[AsyncSession] | None:
    """Return the initialized factory for trusted background workers."""
    return _session_factory


def database_engine() -> AsyncEngine | None:
    """Return the shared engine for secret-free readiness checks."""
    return _engine


async def get_database_session() -> AsyncIterator[AsyncSession]:
    """Yield one transaction-scoped session or a safe configuration error."""
    if _session_factory is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Copy trading storage is not configured",
        )
    async with session_scope(_session_factory) as session:
        yield session


DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
