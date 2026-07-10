import asyncio
import os
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import command
from src.db import health as db_health
from src.db import session as db_session
from src.db.base import APP_SCHEMA, Base, include_app_schema_name

API_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = API_ROOT.parent


def _test_database_url() -> str:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set; PostgreSQL integration test skipped")
    try:
        return db_session.normalize_database_url(database_url)
    except ValueError:
        pytest.fail("TEST_DATABASE_URL must be a PostgreSQL URL")


async def _schema_exists(database_url: str) -> bool:
    engine = db_session.create_database_engine(database_url)
    try:
        async with engine.connect() as connection:
            exists = await connection.scalar(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema_name"
                    ")"
                ),
                {"schema_name": APP_SCHEMA},
            )
            return bool(exists)
    finally:
        await db_session.dispose_database_engine(engine)


def test_base_metadata_uses_app_schema() -> None:
    assert APP_SCHEMA == "app"
    assert Base.metadata.schema == APP_SCHEMA


def test_alembic_name_filter_excludes_auth_owned_schemas() -> None:
    assert include_app_schema_name(APP_SCHEMA, "schema", {}) is True
    assert include_app_schema_name(None, "schema", {}) is False
    assert include_app_schema_name("auth", "schema", {}) is False
    assert include_app_schema_name("strategies", "table", {"schema_name": APP_SCHEMA}) is True
    assert include_app_schema_name("user", "table", {"schema_name": None}) is False
    assert include_app_schema_name("session", "table", {"schema_name": "auth"}) is False


def test_database_engine_enables_pool_health_and_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []
    expected_engine = object()

    def fake_create_async_engine(database_url: str, **options: Any) -> object:
        calls.append((database_url, options))
        return expected_engine

    monkeypatch.setattr(db_session, "create_async_engine", fake_create_async_engine)

    engine = db_session.create_database_engine("postgresql://app_user@localhost/strategy_lab")

    assert engine is expected_engine
    assert calls == [
        (
            "postgresql+asyncpg://app_user@localhost/strategy_lab",
            {
                "max_overflow": 10,
                "pool_pre_ping": True,
                "pool_size": 5,
                "pool_timeout": 5.0,
            },
        )
    ]


async def test_session_scope_commits_on_success() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock(return_value=False)
    session_factory = MagicMock(return_value=session_context)

    async with db_session.session_scope(session_factory) as yielded_session:
        assert yielded_session is session

    session.commit.assert_awaited_once_with()


async def test_session_scope_rolls_back_and_reraises() -> None:
    session = MagicMock()
    session.rollback = AsyncMock()
    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock(return_value=False)
    session_factory = MagicMock(return_value=session_context)

    with pytest.raises(RuntimeError, match="rollback probe"):
        async with db_session.session_scope(session_factory) as yielded_session:
            assert yielded_session is session
            raise RuntimeError("rollback probe")

    session.rollback.assert_awaited_once_with()


def test_session_factory_uses_non_expiring_async_sessions() -> None:
    engine = MagicMock()

    session_factory = db_session.create_session_factory(engine)

    assert session_factory.kw["bind"] is engine
    assert session_factory.kw["autoflush"] is False
    assert session_factory.kw["expire_on_commit"] is False


async def test_dispose_database_engine_supports_graceful_shutdown() -> None:
    engine = MagicMock()
    engine.dispose = AsyncMock()

    await db_session.dispose_database_engine(engine)

    engine.dispose.assert_awaited_once_with()


async def test_database_health_returns_healthy_response() -> None:
    connection = MagicMock()
    connection.execute = AsyncMock()
    connection_context = MagicMock()
    connection_context.__aenter__ = AsyncMock(return_value=connection)
    connection_context.__aexit__ = AsyncMock(return_value=False)
    engine = MagicMock()
    engine.connect.return_value = connection_context

    response = await db_health.check_database_health(engine, timeout_seconds=0.1)

    assert response["status"] == "healthy"
    assert response["latency_ms"] >= 0
    assert "error" not in response
    statement = connection.execute.await_args.args[0]
    assert str(statement) == "SELECT 1"


async def test_database_health_sanitizes_connection_failure() -> None:
    engine = MagicMock()
    engine.connect.side_effect = ConnectionError(
        "could not connect with password=do-not-expose-this"
    )

    response = await db_health.check_database_health(engine, timeout_seconds=0.1)

    assert response["status"] == "unhealthy"
    assert response.get("error") == "connection_failed"
    assert response["latency_ms"] >= 0
    assert "do-not-expose-this" not in str(response)


async def test_database_health_reports_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def slow_ping(engine: object) -> None:
        await asyncio.sleep(1)

    monkeypatch.setattr(db_health, "_ping", slow_ping)

    response = await db_health.check_database_health(MagicMock(), timeout_seconds=0.001)

    assert response["status"] == "unhealthy"
    assert response.get("error") == "timeout"


def test_alembic_revision_template_and_production_artifact_exist() -> None:
    template = API_ROOT / "alembic/script.py.mako"
    assert template.is_file()
    assert "${up_revision}" in template.read_text(encoding="utf-8")

    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY api/alembic.ini ./alembic.ini" in dockerfile
    assert "COPY api/alembic/ ./alembic/" in dockerfile


def test_alembic_version_table_is_explicitly_public(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://app_user@localhost/strategy_lab")
    alembic_config = AlembicConfig(API_ROOT / "alembic.ini")
    output = StringIO()
    alembic_config.output_buffer = output

    command.upgrade(alembic_config, "head", sql=True)

    assert "CREATE TABLE public.alembic_version" in output.getvalue()


def test_initial_migration_only_manages_app_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    alembic_config = AlembicConfig(API_ROOT / "alembic.ini")
    scripts = ScriptDirectory.from_config(alembic_config)
    revision = scripts.get_revision("head")
    assert revision is not None
    assert revision.revision == "0001_app_schema"

    statements: list[object] = []
    monkeypatch.setattr(revision.module.op, "execute", statements.append)

    revision.module.upgrade()
    assert len(statements) == 1
    create_schema = statements.pop()
    assert isinstance(create_schema, CreateSchema)
    assert create_schema.element == APP_SCHEMA
    assert create_schema.if_not_exists is False

    revision.module.downgrade()
    assert len(statements) == 1
    drop_schema = statements.pop()
    assert isinstance(drop_schema, DropSchema)
    assert drop_schema.element == APP_SCHEMA
    assert drop_schema.cascade is False
    assert drop_schema.if_exists is False


@pytest.mark.integration
def test_postgresql_migration_up_and_down(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = _test_database_url()
    monkeypatch.setenv("DATABASE_URL", database_url)
    alembic_config = AlembicConfig(API_ROOT / "alembic.ini")
    assert asyncio.run(_schema_exists(database_url)) is False, (
        "TEST_DATABASE_URL must point to a disposable database without the app schema"
    )

    try:
        command.upgrade(alembic_config, "head")
        assert asyncio.run(_schema_exists(database_url)) is True
    finally:
        command.downgrade(alembic_config, "base")

    assert asyncio.run(_schema_exists(database_url)) is False


@pytest.mark.integration
async def test_postgresql_session_scope_rolls_back_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = _test_database_url()
    monkeypatch.setenv("DATABASE_URL", database_url)
    alembic_config = AlembicConfig(API_ROOT / "alembic.ini")
    assert await _schema_exists(database_url) is False, (
        "TEST_DATABASE_URL must point to a disposable database without the app schema"
    )

    engine = None
    try:
        await asyncio.to_thread(command.upgrade, alembic_config, "head")
        engine = db_session.create_database_engine(database_url)
        async with engine.begin() as connection:
            await connection.execute(text("DROP TABLE IF EXISTS app._transaction_probe"))
            await connection.execute(
                text("CREATE TABLE app._transaction_probe (value INTEGER NOT NULL)")
            )

        session_factory = db_session.create_session_factory(engine)
        with pytest.raises(RuntimeError, match="rollback probe"):
            async with db_session.session_scope(session_factory) as session:
                await session.execute(
                    text("INSERT INTO app._transaction_probe (value) VALUES (1)")
                )
                raise RuntimeError("rollback probe")

        async with engine.connect() as connection:
            row_count = await connection.scalar(
                text("SELECT COUNT(*) FROM app._transaction_probe")
            )
        assert row_count == 0
    finally:
        try:
            if engine is not None:
                try:
                    async with engine.begin() as connection:
                        await connection.execute(
                            text("DROP TABLE IF EXISTS app._transaction_probe")
                        )
                finally:
                    await db_session.dispose_database_engine(engine)
        finally:
            await asyncio.to_thread(command.downgrade, alembic_config, "base")
