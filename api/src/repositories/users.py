"""User profile repository for WorkOS-authenticated application users."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.user import UserProfile, UserRole, UserStatus


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized or "@" not in normalized or len(normalized) > 320:
        raise ValueError("invalid email")
    return normalized


async def create_user_profile(
    session: AsyncSession,
    *,
    auth_subject: str,
    email: str,
    email_verified: bool,
    role: UserRole = UserRole.TRADER,
    status: UserStatus = UserStatus.ACTIVE,
) -> UserProfile:
    """Create a profile for a verified external subject without touching auth tables."""
    subject = auth_subject.strip()
    normalized_email = _normalize_email(email)
    if not subject or len(subject) > 128:
        raise ValueError("invalid auth subject")

    statement = (
        pg_insert(UserProfile)
        .values(
            auth_subject=subject,
            email=normalized_email,
            email_verified=email_verified,
            role=role,
            status=status,
        )
        .on_conflict_do_nothing()
        .returning(UserProfile)
    )
    profile = (await session.execute(statement)).scalar_one_or_none()
    if profile is None:
        raise ValueError("user profile already exists")
    return profile


async def reconcile_verified_user_profile(
    session: AsyncSession,
    *,
    auth_subject: str,
    email: str,
    role: UserRole = UserRole.TRADER,
    status: UserStatus = UserStatus.ACTIVE,
) -> UserProfile:
    """Bind a verified email's durable profile to its current auth subject.

    WorkOS can replace a legacy application's subject while keeping the same
    verified email. The email is the migration key for that transition; foreign
    keys referencing ``auth_subject`` use ``ON UPDATE CASCADE`` so account and
    copy-trading ownership move with the profile atomically.
    """
    subject = auth_subject.strip()
    normalized_email = _normalize_email(email)
    if not subject or len(subject) > 128:
        raise ValueError("invalid auth subject")

    existing = await session.get(UserProfile, subject)
    if existing is not None:
        existing.email = normalized_email
        existing.email_verified = True
        existing.role = role
        existing.status = status
        await session.flush()
        return existing

    statement = (
        pg_insert(UserProfile)
        .values(
            auth_subject=subject,
            email=normalized_email,
            email_verified=True,
            role=role.value,
            status=status.value,
        )
        .on_conflict_do_update(
            index_elements=[UserProfile.email],
            set_={
                "auth_subject": subject,
                "email_verified": True,
                "role": role.value,
                "status": status.value,
            },
        )
        .returning(UserProfile.auth_subject)
    )
    reconciled_subject = (await session.execute(statement)).scalar_one()
    profile = await session.get(UserProfile, reconciled_subject)
    if profile is None:  # pragma: no cover - RETURNING guarantees the row exists.
        raise RuntimeError("reconciled user profile could not be loaded")
    return profile


async def get_user_by_auth_subject(
    session: AsyncSession,
    auth_subject: str,
) -> UserProfile | None:
    """Resolve the application profile by stable WorkOS subject."""
    return await session.scalar(
        select(UserProfile).where(UserProfile.auth_subject == auth_subject.strip())
    )


async def set_user_access(
    session: AsyncSession,
    user_id: str,
    *,
    role: UserRole | None = None,
    status: UserStatus | None = None,
) -> UserProfile:
    """Apply an explicit role/status transition to one app profile."""
    profile = await session.get(UserProfile, user_id)
    if profile is None:
        raise ValueError("user profile not found")
    if role is not None:
        profile.role = role
    if status is not None:
        profile.status = status
    await session.flush()
    return profile
