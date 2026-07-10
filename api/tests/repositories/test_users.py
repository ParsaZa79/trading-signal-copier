from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, cast

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config as AlembicConfig
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Table, inspect, select
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.db import session as db_session
from src.db.base import Base, include_app_schema_name
from src.models.user import UserProfile, UserRole, UserStatus
from src.repositories.users import (
    create_user_profile,
    get_user_by_auth_subject,
    set_user_access,
)

API_ROOT = Path(__file__).resolve().parents[2]


def test_identity_tables_are_the_second_alembic_revision() -> None:
    scripts = ScriptDirectory.from_config(AlembicConfig(API_ROOT / "alembic.ini"))
    head = scripts.get_revision("head")
    assert head is not None
    assert head.revision == "0002_identity_accounts"
    assert head.down_revision == "0001_app_schema"


def test_user_profile_is_owned_by_app_schema_without_auth_foreign_key() -> None:
    table = cast(Table, UserProfile.__table__)

    assert table.schema == "app"
    assert table.name == "app_user_profiles"
    assert table.c.email.unique is True
    assert {column.name for column in table.primary_key} == {"auth_subject"}
    assert "id" not in table.c

    mapper = inspect(UserProfile)
    assert "password" not in mapper.attrs
    assert "credentials" not in mapper.attrs


@pytest.mark.integration
async def test_user_repository_defaults_verified_identity_to_trader(
    repository_session: AsyncSession,
) -> None:
    profile = await create_user_profile(
        repository_session,
        auth_subject="better-auth-user-1",
        email="  TRADER@Example.COM ",
        email_verified=True,
    )
    await repository_session.flush()

    assert profile.auth_subject == "better-auth-user-1"
    assert profile.email == "trader@example.com"
    assert profile.email_verified is True
    assert profile.role is UserRole.TRADER
    assert profile.status is UserStatus.ACTIVE
    assert await get_user_by_auth_subject(repository_session, "better-auth-user-1") is profile


@pytest.mark.integration
async def test_user_access_change_is_explicit_and_persisted(
    repository_session: AsyncSession,
) -> None:
    profile = await create_user_profile(
        repository_session,
        auth_subject="better-auth-user-2",
        email="admin@example.com",
        email_verified=True,
    )

    await set_user_access(
        repository_session,
        profile.auth_subject,
        role=UserRole.ADMIN,
        status=UserStatus.DISABLED,
    )
    await repository_session.flush()

    stored = await repository_session.scalar(
        select(UserProfile).where(UserProfile.auth_subject == profile.auth_subject)
    )
    assert stored is not None
    assert stored.role is UserRole.ADMIN
    assert stored.status is UserStatus.DISABLED


@pytest.mark.integration
async def test_migrated_schema_matches_sqlalchemy_metadata(
    repository_session: AsyncSession,
) -> None:
    connection = await repository_session.connection()

    def compare(connection: Connection) -> list[Any]:
        context = MigrationContext.configure(
            connection,
            opts={
                "include_schemas": True,
                "include_name": include_app_schema_name,
                "compare_type": True,
                "compare_server_default": True,
            },
        )
        return compare_metadata(context, Base.metadata)

    differences = await connection.run_sync(compare)
    assert differences == []


@pytest.mark.integration
async def test_user_subject_and_email_are_unique(repository_session: AsyncSession) -> None:
    await create_user_profile(
        repository_session,
        auth_subject="duplicate-subject",
        email="first@example.com",
        email_verified=True,
    )
    await repository_session.flush()

    with pytest.raises(ValueError, match="already exists"):
        await create_user_profile(
            repository_session,
            auth_subject="duplicate-subject",
            email="second@example.com",
            email_verified=True,
        )


@pytest.mark.integration
async def test_concurrent_user_creation_has_one_clean_winner(
    repository_database_url: str,
) -> None:
    engine = db_session.create_database_engine(repository_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def create_once() -> UserProfile | ValueError:
        async with factory() as session:
            try:
                profile = await create_user_profile(
                    session,
                    auth_subject="concurrent-subject",
                    email="concurrent@example.com",
                    email_verified=True,
                )
                await session.commit()
                return profile
            except ValueError as error:
                await session.rollback()
                return error

    try:
        outcomes = await asyncio.gather(create_once(), create_once())
    finally:
        await engine.dispose()

    assert sum(isinstance(item, UserProfile) for item in outcomes) == 1
    assert sum(isinstance(item, ValueError) for item in outcomes) == 1
