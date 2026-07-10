"""Alembic environment for FastAPI-owned PostgreSQL objects."""

import asyncio
import os

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from src.db.base import Base, include_app_schema_name
from src.db.session import normalize_database_url

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before running Alembic")
    return normalize_database_url(database_url)


def run_migrations_offline() -> None:
    """Run migrations without creating an Engine."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_app_schema_name,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_app_schema_name,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations through SQLAlchemy's async engine bridge."""
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations with a live asyncpg connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
