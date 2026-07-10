"""Trading accounts and explicit user memberships."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Enum, ForeignKey, LargeBinary, String, Uuid
from sqlalchemy.orm import Mapped, deferred, mapped_column

from src.db.base import Base
from src.models.common import TimestampMixin
from src.models.user import _enum_values


class AccountStatus(StrEnum):
    PENDING_SETUP = "pending_setup"
    ACTIVE = "active"
    DISABLED = "disabled"


class MembershipRole(StrEnum):
    OWNER = "owner"
    OPERATOR = "operator"
    VIEWER = "viewer"


class TradingAccount(TimestampMixin, Base):
    """User-owned account metadata with an opaque encrypted credential envelope."""

    __tablename__ = "trading_accounts"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[AccountStatus] = mapped_column(
        Enum(
            AccountStatus,
            name="account_status",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
        default=AccountStatus.PENDING_SETUP,
        server_default=AccountStatus.PENDING_SETUP.value,
    )
    credentials_ciphertext: Mapped[bytes | None] = deferred(
        mapped_column(LargeBinary, nullable=True)
    )


class AccountMembership(Base):
    """Explicit authorization edge between a profile and a trading account."""

    __tablename__ = "account_memberships"

    account_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("app.trading_accounts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(128),
        ForeignKey("app.app_user_profiles.auth_subject", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    role: Mapped[MembershipRole] = mapped_column(
        Enum(
            MembershipRole,
            name="membership_role",
            native_enum=False,
            create_constraint=True,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
