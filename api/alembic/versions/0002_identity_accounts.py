"""Create application profiles, trading accounts, memberships, audit, and legacy aliases.

Revision ID: 0002_identity_accounts
Revises: 0001_app_schema
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_identity_accounts"
down_revision: str | None = "0001_app_schema"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

APP_SCHEMA = "app"


def upgrade() -> None:
    op.create_table(
        "app_user_profiles",
        sa.Column("auth_subject", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("role", sa.String(length=6), server_default="trader", nullable=False),
        sa.Column("status", sa.String(length=8), server_default="active", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'trader', 'viewer')",
            name="user_role",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'pending')",
            name="user_status",
        ),
        sa.PrimaryKeyConstraint("auth_subject"),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_app_user_profiles_email",
        "app_user_profiles",
        ["email"],
        unique=True,
        schema=APP_SCHEMA,
    )

    op.create_table(
        "trading_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.String(length=13),
            server_default="pending_setup",
            nullable=False,
        ),
        sa.Column("credentials_ciphertext", sa.LargeBinary(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending_setup', 'active', 'disabled')",
            name="account_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=APP_SCHEMA,
    )

    op.create_table(
        "account_memberships",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=8), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'operator', 'viewer')",
            name="membership_role",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["app.trading_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app.app_user_profiles.auth_subject"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("account_id", "user_id"),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_account_memberships_user_id",
        "account_memberships",
        ["user_id"],
        unique=False,
        schema=APP_SCHEMA,
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.String(length=128),
            nullable=True,
            comment="Immutable actor auth subject; intentionally not a foreign key",
        ),
        sa.Column("action", sa.String(length=160), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=False),
        sa.Column("target_id", sa.String(length=200), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_audit_events_action",
        "audit_events",
        ["action"],
        unique=False,
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_audit_events_actor_user_id",
        "audit_events",
        ["actor_user_id"],
        unique=False,
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_audit_events_target",
        "audit_events",
        ["target_type", "target_id"],
        unique=False,
        schema=APP_SCHEMA,
    )
    op.execute(
        """
        CREATE FUNCTION app.reject_audit_event_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events are append-only';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_audit_events_append_only
        BEFORE UPDATE OR DELETE ON app.audit_events
        FOR EACH ROW EXECUTE FUNCTION app.reject_audit_event_mutation()
        """
    )

    op.create_table(
        "legacy_identity_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("legacy_id", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app.app_user_profiles.auth_subject"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source",
            "legacy_id",
            name="uq_legacy_identity_source_id",
        ),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_legacy_identity_aliases_user_id",
        "legacy_identity_aliases",
        ["user_id"],
        unique=False,
        schema=APP_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("legacy_identity_aliases", schema=APP_SCHEMA)
    op.drop_table("audit_events", schema=APP_SCHEMA)
    op.execute("DROP FUNCTION app.reject_audit_event_mutation()")
    op.drop_table("account_memberships", schema=APP_SCHEMA)
    op.drop_table("trading_accounts", schema=APP_SCHEMA)
    op.drop_table("app_user_profiles", schema=APP_SCHEMA)
