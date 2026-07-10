from __future__ import annotations

import asyncio
from typing import cast
from uuid import UUID

import pytest
from sqlalchemy import Table, inspect, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.credential_envelope import seal_credentials, unseal_credentials
from src.db import session as db_session
from src.models.account import AccountMembership, MembershipRole, TradingAccount
from src.models.audit import AuditEvent, LegacyIdentityAlias
from src.models.user import UserRole
from src.repositories.accounts import (
    add_account_member,
    append_audit_event,
    create_trading_account,
    get_encrypted_credentials_for_runtime,
    link_legacy_identity,
    list_accounts_for_user,
    remove_account_member,
)
from src.repositories.users import create_user_profile


def test_account_and_audit_models_never_expose_plaintext_secret_columns() -> None:
    account_table = cast(Table, TradingAccount.__table__)
    assert account_table.schema == "app"
    assert account_table.name == "trading_accounts"
    assert account_table.c.credentials_ciphertext.nullable is True
    assert "password" not in account_table.c
    assert "secret" not in account_table.c

    assert AccountMembership.__table__.schema == "app"
    assert AuditEvent.__table__.schema == "app"
    assert LegacyIdentityAlias.__table__.schema == "app"
    membership_table = cast(Table, AccountMembership.__table__)
    assert {column.name for column in membership_table.primary_key} == {
        "account_id",
        "user_id",
    }
    assert "credentials_ciphertext" in inspect(TradingAccount).attrs


@pytest.mark.integration
async def test_account_repository_returns_secret_free_summaries_and_isolates_members(
    repository_session: AsyncSession,
) -> None:
    owner = await create_user_profile(
        repository_session,
        auth_subject="account-owner",
        email="owner@example.com",
        email_verified=True,
    )
    outsider = await create_user_profile(
        repository_session,
        auth_subject="account-outsider",
        email="outsider@example.com",
        email_verified=True,
    )
    encrypted = seal_credentials(
        {"MT5_LOGIN": "123456", "MT5_PASSWORD": "broker-password", "MT5_SERVER": "Demo"}
    )

    account = await create_trading_account(
        repository_session,
        owner_user_id=owner.auth_subject,
        name="Primary",
        credentials_ciphertext=encrypted,
    )
    await repository_session.flush()

    summaries = await list_accounts_for_user(repository_session, owner.auth_subject)
    assert len(summaries) == 1
    assert summaries[0].id == account.id
    assert summaries[0].name == "Primary"
    assert not hasattr(account, "credentials_ciphertext")
    assert not hasattr(summaries[0], "credentials_ciphertext")
    assert await list_accounts_for_user(repository_session, outsider.auth_subject) == []
    stored_envelope = await get_encrypted_credentials_for_runtime(
        repository_session,
        actor_user_id=owner.auth_subject,
        account_id=account.id,
    )
    assert stored_envelope == encrypted
    assert stored_envelope is not None
    assert unseal_credentials(stored_envelope) == {
        "MT5_LOGIN": "123456",
        "MT5_PASSWORD": "broker-password",
        "MT5_SERVER": "Demo",
    }

    with pytest.raises(PermissionError, match="runtime credential access"):
        await get_encrypted_credentials_for_runtime(
            repository_session,
            actor_user_id=outsider.auth_subject,
            account_id=account.id,
        )


@pytest.mark.integration
async def test_account_membership_grants_explicit_visibility(
    repository_session: AsyncSession,
) -> None:
    owner = await create_user_profile(
        repository_session,
        auth_subject="membership-owner",
        email="membership-owner@example.com",
        email_verified=True,
    )
    viewer = await create_user_profile(
        repository_session,
        auth_subject="membership-viewer",
        email="membership-viewer@example.com",
        email_verified=True,
    )
    account = await create_trading_account(
        repository_session,
        owner_user_id=owner.auth_subject,
        name="Shared",
    )

    await add_account_member(
        repository_session,
        actor_user_id=owner.auth_subject,
        account_id=account.id,
        user_id=viewer.auth_subject,
        role=MembershipRole.VIEWER,
    )
    await repository_session.flush()

    summaries = await list_accounts_for_user(repository_session, viewer.auth_subject)
    assert [summary.id for summary in summaries] == [account.id]
    assert summaries[0].membership_role is MembershipRole.VIEWER


@pytest.mark.integration
async def test_membership_mutations_require_account_owner_or_platform_admin(
    repository_session: AsyncSession,
) -> None:
    owner = await create_user_profile(
        repository_session,
        auth_subject="authorization-owner",
        email="authorization-owner@example.com",
        email_verified=True,
    )
    outsider = await create_user_profile(
        repository_session,
        auth_subject="authorization-outsider",
        email="authorization-outsider@example.com",
        email_verified=True,
    )
    platform_admin = await create_user_profile(
        repository_session,
        auth_subject="authorization-admin",
        email="authorization-admin@example.com",
        email_verified=True,
        role=UserRole.ADMIN,
    )
    account = await create_trading_account(
        repository_session,
        owner_user_id=owner.auth_subject,
        name="Authorized",
    )

    with pytest.raises(PermissionError, match="membership administrator"):
        await add_account_member(
            repository_session,
            actor_user_id=outsider.auth_subject,
            account_id=account.id,
            user_id=outsider.auth_subject,
            role=MembershipRole.VIEWER,
        )

    membership = await add_account_member(
        repository_session,
        actor_user_id=platform_admin.auth_subject,
        account_id=account.id,
        user_id=outsider.auth_subject,
        role=MembershipRole.VIEWER,
    )
    assert membership.role is MembershipRole.VIEWER


@pytest.mark.integration
async def test_membership_mutations_preserve_at_least_one_account_owner(
    repository_session: AsyncSession,
) -> None:
    owner = await create_user_profile(
        repository_session,
        auth_subject="sole-owner",
        email="sole-owner@example.com",
        email_verified=True,
    )
    second_owner = await create_user_profile(
        repository_session,
        auth_subject="second-owner",
        email="second-owner@example.com",
        email_verified=True,
    )
    account = await create_trading_account(
        repository_session,
        owner_user_id=owner.auth_subject,
        name="Owner invariant",
    )

    with pytest.raises(ValueError, match="at least one account owner"):
        await add_account_member(
            repository_session,
            actor_user_id=owner.auth_subject,
            account_id=account.id,
            user_id=owner.auth_subject,
            role=MembershipRole.VIEWER,
        )

    await add_account_member(
        repository_session,
        actor_user_id=owner.auth_subject,
        account_id=account.id,
        user_id=second_owner.auth_subject,
        role=MembershipRole.OWNER,
    )
    await add_account_member(
        repository_session,
        actor_user_id=second_owner.auth_subject,
        account_id=account.id,
        user_id=owner.auth_subject,
        role=MembershipRole.VIEWER,
    )

    with pytest.raises(ValueError, match="at least one account owner"):
        await remove_account_member(
            repository_session,
            actor_user_id=second_owner.auth_subject,
            account_id=account.id,
            user_id=second_owner.auth_subject,
        )


def test_credential_envelope_round_trip_is_cryptographically_valid() -> None:
    plaintext = {"MT5_LOGIN": "123456", "MT5_PASSWORD": "broker-password"}
    envelope = seal_credentials(plaintext)

    assert envelope.startswith(b"fernet:v1:")
    assert b"broker-password" not in envelope
    assert unseal_credentials(envelope) == plaintext


@pytest.mark.integration
@pytest.mark.parametrize(
    "unsafe_payload",
    [
        b"broker-password",
        b"fernet:opaque-ciphertext",
        b"fernet:v1:",
        b"fernet:v1:broker-password",
    ],
)
async def test_credentials_must_be_a_valid_encrypted_envelope(
    repository_session: AsyncSession,
    unsafe_payload: bytes,
) -> None:
    owner = await create_user_profile(
        repository_session,
        auth_subject="plaintext-owner",
        email="plaintext-owner@example.com",
        email_verified=True,
    )

    with pytest.raises(ValueError, match="encrypted envelope"):
        await create_trading_account(
            repository_session,
            owner_user_id=owner.auth_subject,
            name="Unsafe",
            credentials_ciphertext=unsafe_payload,
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    "secret_key",
    [
        "privateKey",
        "Authorization",
        "Cookie",
        "sessionId",
        "passphrase",
        "access-key",
        "client_secret",
        "api_key",
        "refreshToken",
        "encryption_key",
        "jwt",
        "otp",
        "pin",
        "message",
    ],
)
async def test_audit_details_reject_secret_bearing_keys(
    repository_session: AsyncSession,
    secret_key: str,
) -> None:
    actor = await create_user_profile(
        repository_session,
        auth_subject="audit-actor",
        email="audit@example.com",
        email_verified=True,
    )

    event = await append_audit_event(
        repository_session,
        actor_user_id=actor.auth_subject,
        action="account.created",
        target_type="trading_account",
        target_id="account-1",
        details={"source": "dashboard"},
    )
    assert isinstance(event.id, UUID)

    updated = await append_audit_event(
        repository_session,
        actor_user_id=actor.auth_subject,
        action="account.updated",
        target_type="trading_account",
        target_id="account-1",
        details={"source": "dashboard", "changed_fields": ["name", "status"]},
    )
    assert updated.details == {"source": "dashboard", "changed_fields": ["name", "status"]}

    with pytest.raises(ValueError, match="audit details"):
        await append_audit_event(
            repository_session,
            actor_user_id=actor.auth_subject,
            action="account.updated",
            target_type="trading_account",
            target_id="account-1",
            details={"nested": [{secret_key: "must-not-log"}]},
        )


@pytest.mark.integration
async def test_audit_events_are_database_enforced_append_only(
    repository_session: AsyncSession,
) -> None:
    actor = await create_user_profile(
        repository_session,
        auth_subject="immutable-audit-actor",
        email="immutable-audit@example.com",
        email_verified=True,
    )
    event = await append_audit_event(
        repository_session,
        actor_user_id=actor.auth_subject,
        action="account.created",
        target_type="trading_account",
        target_id="immutable-account",
        details={"source": "system"},
    )

    with pytest.raises(DBAPIError):
        async with repository_session.begin_nested():
            await repository_session.execute(
                text("UPDATE app.audit_events SET action = 'tampered' WHERE id = :id"),
                {"id": event.id},
            )

    with pytest.raises(DBAPIError):
        async with repository_session.begin_nested():
            await repository_session.execute(
                text("DELETE FROM app.audit_events WHERE id = :id"),
                {"id": event.id},
            )

    assert await repository_session.get(AuditEvent, event.id) is event


@pytest.mark.integration
async def test_concurrent_membership_grants_are_race_safe(
    repository_database_url: str,
) -> None:
    engine = db_session.create_database_engine(repository_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        owner = await create_user_profile(
            session,
            auth_subject="concurrent-membership-owner",
            email="concurrent-membership-owner@example.com",
            email_verified=True,
        )
        target = await create_user_profile(
            session,
            auth_subject="concurrent-membership-target",
            email="concurrent-membership-target@example.com",
            email_verified=True,
        )
        account = await create_trading_account(
            session,
            owner_user_id=owner.auth_subject,
            name="Concurrent membership",
        )
        await session.commit()

    async def grant_once(role: MembershipRole) -> AccountMembership:
        async with factory() as session:
            membership = await add_account_member(
                session,
                actor_user_id=owner.auth_subject,
                account_id=account.id,
                user_id=target.auth_subject,
                role=role,
            )
            await session.commit()
            return membership

    try:
        outcomes = await asyncio.gather(
            grant_once(MembershipRole.VIEWER),
            grant_once(MembershipRole.OPERATOR),
        )
        async with factory() as session:
            memberships = (
                (
                    await session.execute(
                        select(AccountMembership).where(
                            AccountMembership.account_id == account.id,
                            AccountMembership.user_id == target.auth_subject,
                        )
                    )
                )
                .scalars()
                .all()
            )
    finally:
        await engine.dispose()

    assert len(outcomes) == 2
    assert len(memberships) == 1
    assert memberships[0].role in {MembershipRole.VIEWER, MembershipRole.OPERATOR}


@pytest.mark.integration
async def test_legacy_identity_link_is_idempotent(repository_session: AsyncSession) -> None:
    user = await create_user_profile(
        repository_session,
        auth_subject="legacy-user",
        email="legacy@example.com",
        email_verified=True,
    )

    first = await link_legacy_identity(
        repository_session,
        user_id=user.auth_subject,
        source="clerk",
        legacy_id="user_legacy_123",
    )
    second = await link_legacy_identity(
        repository_session,
        user_id=user.auth_subject,
        source="clerk",
        legacy_id="user_legacy_123",
    )

    assert first.id == second.id


@pytest.mark.integration
async def test_concurrent_legacy_links_are_idempotent(
    repository_database_url: str,
) -> None:
    engine = db_session.create_database_engine(repository_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        user = await create_user_profile(
            session,
            auth_subject="concurrent-legacy-user",
            email="concurrent-legacy@example.com",
            email_verified=True,
        )
        await session.commit()

    async def link_once() -> LegacyIdentityAlias:
        async with factory() as session:
            alias = await link_legacy_identity(
                session,
                user_id=user.auth_subject,
                source="clerk",
                legacy_id="concurrent-legacy-id",
            )
            await session.commit()
            return alias

    try:
        first_result, second_result = await asyncio.gather(link_once(), link_once())
    finally:
        await engine.dispose()

    assert first_result.id == second_result.id
