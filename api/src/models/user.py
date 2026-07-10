"""Application user profile linked to an external Better Auth subject."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Boolean, Enum, String, false
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base
from src.models.common import TimestampMixin


class UserRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    PENDING = "pending"


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    return [member.value for member in enum_type]


class UserProfile(TimestampMixin, Base):
    """FastAPI-owned profile; authentication tables remain outside this model."""

    __tablename__ = "app_user_profiles"

    auth_subject: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=UserRole.TRADER,
        server_default=UserRole.TRADER.value,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
    )
