"""Trading-account, membership, audit, and legacy identity repositories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.credential_envelope import validate_credentials_envelope
from src.models.account import AccountMembership, AccountStatus, MembershipRole, TradingAccount
from src.models.audit import AuditEvent, LegacyIdentityAlias
from src.models.user import UserProfile, UserRole, UserStatus

_AUDIT_DETAIL_SCHEMAS = {
    "account.created": frozenset({"source"}),
    "account.updated": frozenset({"source", "changed_fields"}),
}
_AUDIT_SOURCES = frozenset({"api", "dashboard", "migration", "system"})
_AUDIT_ACCOUNT_FIELDS = frozenset({"credentials", "memberships", "name", "status"})
_MAX_AUDIT_DETAILS_BYTES = 16_384


@dataclass(frozen=True, slots=True)
class AccountSummary:
    """Secret-free account projection safe for API serializers."""

    id: UUID
    name: str
    status: AccountStatus
    membership_role: MembershipRole


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > 120:
        raise ValueError("invalid account name")
    return cleaned


def _validate_audit_details(action: str, details: dict[str, Any]) -> None:
    allowed_keys = _AUDIT_DETAIL_SCHEMAS.get(action)
    if allowed_keys is None:
        if details:
            raise ValueError("audit details are not registered for this action")
        return

    unexpected = set(details) - allowed_keys
    if unexpected:
        raise ValueError(f"audit details contain unsupported fields: {sorted(unexpected)}")

    source = details.get("source")
    if source is not None and source not in _AUDIT_SOURCES:
        raise ValueError("audit details contain an invalid source")

    changed_fields = details.get("changed_fields")
    if changed_fields is not None:
        if not isinstance(changed_fields, list) or not changed_fields:
            raise ValueError("audit changed_fields must be a non-empty list")
        if any(
            not isinstance(field, str) or field not in _AUDIT_ACCOUNT_FIELDS
            for field in changed_fields
        ):
            raise ValueError("audit changed_fields contain an unsupported field")
        if len(changed_fields) != len(set(changed_fields)):
            raise ValueError("audit changed_fields must be unique")


async def create_trading_account(
    session: AsyncSession,
    *,
    owner_user_id: str,
    name: str,
    credentials_ciphertext: bytes | None = None,
) -> AccountSummary:
    """Create an account and its owner membership atomically in the caller's UoW."""
    if await session.get(UserProfile, owner_user_id) is None:
        raise ValueError("owner user not found")
    if credentials_ciphertext is not None:
        validate_credentials_envelope(credentials_ciphertext)

    account = TradingAccount(
        name=_clean_name(name),
        credentials_ciphertext=credentials_ciphertext,
    )
    session.add(account)
    await session.flush()
    session.add(
        AccountMembership(
            account_id=account.id,
            user_id=owner_user_id,
            role=MembershipRole.OWNER,
        )
    )
    await session.flush()
    return AccountSummary(
        id=account.id,
        name=account.name,
        status=account.status,
        membership_role=MembershipRole.OWNER,
    )


async def add_account_member(
    session: AsyncSession,
    *,
    actor_user_id: str,
    account_id: UUID,
    user_id: str,
    role: MembershipRole,
) -> AccountMembership:
    """Grant or update one membership after serialized authorization checks."""
    await _lock_account_and_authorize_membership_change(
        session,
        account_id=account_id,
        actor_user_id=actor_user_id,
    )
    if await session.get(UserProfile, user_id) is None:
        raise ValueError("user profile not found")

    membership = await session.get(AccountMembership, (account_id, user_id))
    if (
        membership is not None
        and membership.role is MembershipRole.OWNER
        and role is not MembershipRole.OWNER
    ):
        await _require_another_account_owner(session, account_id)

    statement = (
        pg_insert(AccountMembership)
        .values(account_id=account_id, user_id=user_id, role=role.value)
        .on_conflict_do_update(
            index_elements=["account_id", "user_id"],
            set_={"role": role.value},
        )
    )
    await session.execute(statement)
    membership = await session.scalar(
        select(AccountMembership)
        .where(
            AccountMembership.account_id == account_id,
            AccountMembership.user_id == user_id,
        )
        .execution_options(populate_existing=True)
    )
    if membership is None:
        raise RuntimeError("membership upsert did not resolve")
    return membership


async def remove_account_member(
    session: AsyncSession,
    *,
    actor_user_id: str,
    account_id: UUID,
    user_id: str,
) -> bool:
    """Remove a membership while preserving authorization and owner invariants."""
    await _lock_account_and_authorize_membership_change(
        session,
        account_id=account_id,
        actor_user_id=actor_user_id,
    )
    membership = await session.get(AccountMembership, (account_id, user_id))
    if membership is None:
        return False
    if membership.role is MembershipRole.OWNER:
        await _require_another_account_owner(session, account_id)
    await session.delete(membership)
    await session.flush()
    return True


async def _lock_account_and_authorize_membership_change(
    session: AsyncSession,
    *,
    account_id: UUID,
    actor_user_id: str,
) -> TradingAccount:
    account = await session.scalar(
        select(TradingAccount).where(TradingAccount.id == account_id).with_for_update()
    )
    if account is None:
        raise ValueError("trading account not found")

    actor = await session.get(UserProfile, actor_user_id)
    if actor is None or actor.status is not UserStatus.ACTIVE:
        raise PermissionError("account membership administrator required")
    if actor.role in {UserRole.OWNER, UserRole.ADMIN}:
        return account

    actor_membership = await session.get(AccountMembership, (account_id, actor_user_id))
    if actor_membership is None or actor_membership.role is not MembershipRole.OWNER:
        raise PermissionError("account membership administrator required")
    return account


async def _require_another_account_owner(session: AsyncSession, account_id: UUID) -> None:
    owner_count = await session.scalar(
        select(func.count())
        .select_from(AccountMembership)
        .where(
            AccountMembership.account_id == account_id,
            AccountMembership.role == MembershipRole.OWNER,
        )
    )
    if not owner_count or owner_count <= 1:
        raise ValueError("at least one account owner is required")


async def list_accounts_for_user(
    session: AsyncSession,
    user_id: str,
) -> list[AccountSummary]:
    """Return only secret-free accounts visible through an explicit membership."""
    rows = (
        await session.execute(
            select(TradingAccount, AccountMembership.role)
            .join(AccountMembership, AccountMembership.account_id == TradingAccount.id)
            .where(AccountMembership.user_id == user_id)
            .order_by(TradingAccount.created_at, TradingAccount.id)
        )
    ).all()
    return [
        AccountSummary(
            id=account.id,
            name=account.name,
            status=account.status,
            membership_role=membership_role,
        )
        for account, membership_role in rows
    ]


async def get_encrypted_credentials_for_runtime(
    session: AsyncSession,
    *,
    actor_user_id: str,
    account_id: UUID,
) -> bytes | None:
    """Load an envelope only for an active privileged user or account operator."""
    actor = await session.get(UserProfile, actor_user_id)
    if actor is None or actor.status is not UserStatus.ACTIVE:
        raise PermissionError("runtime credential access required")
    if actor.role not in {UserRole.OWNER, UserRole.ADMIN}:
        membership = await session.get(AccountMembership, (account_id, actor_user_id))
        if membership is None or membership.role not in {
            MembershipRole.OWNER,
            MembershipRole.OPERATOR,
        }:
            raise PermissionError("runtime credential access required")

    return await session.scalar(
        select(TradingAccount.credentials_ciphertext).where(TradingAccount.id == account_id)
    )


async def append_audit_event(
    session: AsyncSession,
    *,
    actor_user_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append a bounded event whose details conform to its registered safe schema."""
    clean_action = action.strip()
    clean_target_type = target_type.strip()
    clean_target_id = target_id.strip()
    if not clean_action or not clean_target_type or not clean_target_id:
        raise ValueError("audit action and target are required")

    safe_details = details or {}
    _validate_audit_details(clean_action, safe_details)
    try:
        serialized = json.dumps(safe_details, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as error:
        raise ValueError("audit details must be JSON serializable") from error
    if len(serialized.encode("utf-8")) > _MAX_AUDIT_DETAILS_BYTES:
        raise ValueError("audit details exceed size limit")

    event = AuditEvent(
        actor_user_id=actor_user_id,
        action=clean_action,
        target_type=clean_target_type,
        target_id=clean_target_id,
        details=json.loads(serialized),
    )
    session.add(event)
    await session.flush()
    return event


async def link_legacy_identity(
    session: AsyncSession,
    *,
    user_id: str,
    source: str,
    legacy_id: str,
) -> LegacyIdentityAlias:
    """Create or return one idempotent legacy identity mapping."""
    clean_source = source.strip().lower()
    clean_legacy_id = legacy_id.strip()
    if not clean_source or not clean_legacy_id:
        raise ValueError("legacy source and id are required")

    if await session.get(UserProfile, user_id) is None:
        raise ValueError("user profile not found")

    alias_id = uuid4()
    statement = (
        pg_insert(LegacyIdentityAlias)
        .values(
            id=alias_id,
            user_id=user_id,
            source=clean_source,
            legacy_id=clean_legacy_id,
        )
        .on_conflict_do_nothing(index_elements=["source", "legacy_id"])
        .returning(LegacyIdentityAlias)
    )
    created = (await session.execute(statement)).scalar_one_or_none()
    if created is not None:
        return created

    existing = await session.scalar(
        select(LegacyIdentityAlias).where(
            LegacyIdentityAlias.source == clean_source,
            LegacyIdentityAlias.legacy_id == clean_legacy_id,
        )
    )
    if existing is None:
        raise RuntimeError("legacy identity conflict did not resolve")
    if existing.user_id != user_id:
        raise ValueError("legacy identity already belongs to another user")
    return existing
