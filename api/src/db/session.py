"""Async PostgreSQL engine and session lifecycle helpers."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DEFAULT_POOL_SIZE = 5
DEFAULT_MAX_OVERFLOW = 10
DEFAULT_POOL_TIMEOUT_SECONDS = 5.0


def normalize_database_url(database_url: str) -> str:
    """Return a PostgreSQL URL configured for SQLAlchemy's asyncpg dialect."""
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    raise ValueError("database URL must use PostgreSQL with the asyncpg driver")


def create_database_engine(
    database_url: str,
    *,
    pool_size: int = DEFAULT_POOL_SIZE,
    max_overflow: int = DEFAULT_MAX_OVERFLOW,
    pool_timeout: float = DEFAULT_POOL_TIMEOUT_SECONDS,
) -> AsyncEngine:
    """Build an async PostgreSQL engine without opening a connection eagerly."""
    return create_async_engine(
        normalize_database_url(database_url),
        max_overflow=max_overflow,
        pool_pre_ping=True,
        pool_size=pool_size,
        pool_timeout=pool_timeout,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the async session factory used by request-scoped units of work."""
    return async_sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


async def dispose_database_engine(engine: AsyncEngine) -> None:
    """Drain and close the engine pool during application shutdown."""
    await engine.dispose()


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a session and roll its transaction back when the unit of work fails."""
    async with session_factory() as session:
        try:
            yield session
        except BaseException:
            await session.rollback()
            raise
        else:
            await session.commit()
