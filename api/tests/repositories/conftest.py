from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from alembic import command
from src.db import session as db_session
from src.db.base import APP_SCHEMA

API_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session", autouse=True)
def repository_credential_secret() -> Iterator[None]:
    previous = os.environ.get("APP_SECRET_KEY")
    os.environ["APP_SECRET_KEY"] = "repository-tests-only-not-a-production-secret"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("APP_SECRET_KEY", None)
        else:
            os.environ["APP_SECRET_KEY"] = previous


async def _schema_exists(database_url: str) -> bool:
    engine = db_session.create_database_engine(database_url)
    try:
        async with engine.connect() as connection:
            return bool(
                await connection.scalar(
                    text(
                        "SELECT EXISTS ("
                        "SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"
                        ")"
                    ),
                    {"schema": APP_SCHEMA},
                )
            )
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
def repository_database_url() -> Iterator[str]:
    """Migrate one disposable database without sharing async engines across loops."""
    raw_url = os.getenv("TEST_DATABASE_URL")
    if not raw_url:
        pytest.skip("TEST_DATABASE_URL is not set; repository integration tests skipped")
    database_url = db_session.normalize_database_url(raw_url)
    assert not asyncio.run(_schema_exists(database_url)), "TEST_DATABASE_URL must be disposable"

    config = AlembicConfig(API_ROOT / "alembic.ini")
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    command.upgrade(config, "head")
    try:
        yield database_url
    finally:
        command.downgrade(config, "base")
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url


@pytest_asyncio.fixture
async def repository_session(
    repository_database_url: str,
) -> AsyncIterator[AsyncSession]:
    engine = db_session.create_database_engine(repository_database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            factory = async_sessionmaker(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )
            async with factory() as session:
                yield session
            await transaction.rollback()
    finally:
        await engine.dispose()
