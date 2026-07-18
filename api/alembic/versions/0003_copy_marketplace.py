"""Create the durable account-scoped copy-trading marketplace.

Revision ID: 0003_copy_marketplace
Revises: 0002_identity_accounts
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_copy_marketplace"
down_revision: str | None = "0002_identity_accounts"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

APP_SCHEMA = "app"


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "copy_legacy_archive",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("record_type", sa.String(length=40), nullable=False),
        sa.Column("legacy_id", sa.String(length=200), nullable=False),
        sa.Column("owner_user_id", sa.String(length=128), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("paper_only", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "record_type", "legacy_id", name="uq_copy_legacy_archive_record"
        ),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_legacy_archive_owner_user_id",
        "copy_legacy_archive",
        ["owner_user_id"],
        schema=APP_SCHEMA,
    )

    op.create_table(
        "copy_trader_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("is_copyable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "markets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "statistics",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("stats_updated_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["account_id"], ["app.trading_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["app.app_user_profiles.auth_subject"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_trader_profiles_account_id",
        "copy_trader_profiles",
        ["account_id"],
        unique=True,
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_trader_profiles_owner_user_id",
        "copy_trader_profiles",
        ["owner_user_id"],
        schema=APP_SCHEMA,
    )

    op.create_table(
        "copy_risk_policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("preset", sa.String(length=12), server_default="conservative", nullable=False),
        sa.Column("risk_per_trade_pct", sa.Float(), server_default="0.25", nullable=False),
        sa.Column("daily_loss_limit_pct", sa.Float(), server_default="1", nullable=False),
        sa.Column("total_open_risk_pct", sa.Float(), server_default="1", nullable=False),
        sa.Column("max_open_trades", sa.Integer(), server_default="3", nullable=False),
        sa.Column("require_stop_loss", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "allowed_symbols",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "preset IN ('conservative', 'balanced', 'custom')", name="copy_risk_preset"
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["app.trading_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_risk_policies_account_id",
        "copy_risk_policies",
        ["account_id"],
        unique=True,
        schema=APP_SCHEMA,
    )

    op.create_table(
        "copy_jurisdiction_policies",
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("live_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("disclosure_version", sa.String(length=80), nullable=True),
        sa.Column(
            "requirements",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *_timestamps(),
        sa.PrimaryKeyConstraint("country_code"),
        schema=APP_SCHEMA,
    )

    op.create_table(
        "copy_runtimes",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=8), server_default="offline", nullable=False),
        sa.Column("runtime_ref", sa.String(length=160), nullable=True),
        sa.Column("broker_server", sa.String(length=160), nullable=True),
        sa.Column("trading_enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('offline', 'starting', 'healthy', 'degraded')",
            name="copy_runtime_status",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["app.trading_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("account_id"),
        schema=APP_SCHEMA,
    )

    op.create_table(
        "copy_subscriptions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trader_id", sa.Uuid(), nullable=False),
        sa.Column("follower_account_id", sa.Uuid(), nullable=False),
        sa.Column("follower_user_id", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=5), server_default="paper", nullable=False),
        sa.Column("status", sa.String(length=8), server_default="active", nullable=False),
        sa.Column(
            "risk_preset", sa.String(length=12), server_default="conservative", nullable=False
        ),
        sa.Column(
            "overlap_acknowledged", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("disclosure_version", sa.String(length=80), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("live_activated_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("mode IN ('paper', 'live')", name="copy_mode"),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'paused', 'stopping', 'stopped')",
            name="copy_subscription_status",
        ),
        sa.CheckConstraint(
            "risk_preset IN ('conservative', 'balanced', 'custom')",
            name="copy_subscription_risk_preset",
        ),
        sa.ForeignKeyConstraint(
            ["trader_id"], ["app.copy_trader_profiles.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["follower_account_id"], ["app.trading_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["follower_user_id"],
            ["app.app_user_profiles.auth_subject"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trader_id", "follower_account_id", name="uq_copy_subscription_trader_account"
        ),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_subscriptions_trader_id",
        "copy_subscriptions",
        ["trader_id"],
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_subscriptions_follower_account_id",
        "copy_subscriptions",
        ["follower_account_id"],
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_subscriptions_follower_user_id",
        "copy_subscriptions",
        ["follower_user_id"],
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_copy_subscriptions_follower_status",
        "copy_subscriptions",
        ["follower_user_id", "status"],
        schema=APP_SCHEMA,
    )

    op.create_table(
        "copy_trade_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trader_id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("source_ticket", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=6), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=True),
        sa.Column(
            "take_profits",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_volume", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint(
            "action IN ('open', 'modify', 'reduce', 'close')",
            name="copy_trade_action",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'failed')",
            name="copy_event_status",
        ),
        sa.ForeignKeyConstraint(
            ["trader_id"], ["app.copy_trader_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trader_id", "external_id", name="uq_copy_event_trader_external"),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_trade_events_trader_id",
        "copy_trade_events",
        ["trader_id"],
        schema=APP_SCHEMA,
    )

    op.create_table(
        "copy_outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trade_event_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["trade_event_id"], ["app.copy_trade_events.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trade_event_id"),
        schema=APP_SCHEMA,
    )

    op.create_table(
        "copy_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("trade_event_id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("follower_account_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=5), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("desired_volume", sa.Float(), nullable=True),
        sa.Column("actual_volume", sa.Float(), nullable=True),
        sa.Column("blocked_reason", sa.String(length=120), nullable=True),
        sa.Column("target_ticket", sa.String(length=100), nullable=True),
        sa.Column("realized_pnl", sa.Float(), server_default="0", nullable=False),
        sa.Column(
            "broker_result",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        *_timestamps(),
        sa.CheckConstraint("mode IN ('paper', 'live')", name="copy_execution_mode"),
        sa.CheckConstraint(
            "status IN ('accepted', 'blocked', 'pending', 'executed', 'failed')",
            name="copy_execution_status",
        ),
        sa.ForeignKeyConstraint(
            ["trade_event_id"], ["app.copy_trade_events.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["app.copy_subscriptions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["follower_account_id"], ["app.trading_accounts.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trade_event_id", "subscription_id", name="uq_copy_execution_event_sub"
        ),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_executions_trade_event_id",
        "copy_executions",
        ["trade_event_id"],
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_executions_subscription_id",
        "copy_executions",
        ["subscription_id"],
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_executions_follower_account_id",
        "copy_executions",
        ["follower_account_id"],
        schema=APP_SCHEMA,
    )

    op.create_table(
        "copy_ticket_mappings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("source_ticket", sa.String(length=100), nullable=False),
        sa.Column("target_ticket", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=40), nullable=False),
        sa.Column("is_open", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["subscription_id"], ["app.copy_subscriptions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "subscription_id", "source_ticket", name="uq_copy_ticket_subscription_source"
        ),
        schema=APP_SCHEMA,
    )
    op.create_index(
        "ix_app_copy_ticket_mappings_subscription_id",
        "copy_ticket_mappings",
        ["subscription_id"],
        schema=APP_SCHEMA,
    )


def downgrade() -> None:
    op.drop_table("copy_ticket_mappings", schema=APP_SCHEMA)
    op.drop_table("copy_executions", schema=APP_SCHEMA)
    op.drop_table("copy_outbox_events", schema=APP_SCHEMA)
    op.drop_table("copy_trade_events", schema=APP_SCHEMA)
    op.drop_table("copy_subscriptions", schema=APP_SCHEMA)
    op.drop_table("copy_runtimes", schema=APP_SCHEMA)
    op.drop_table("copy_jurisdiction_policies", schema=APP_SCHEMA)
    op.drop_table("copy_risk_policies", schema=APP_SCHEMA)
    op.drop_table("copy_trader_profiles", schema=APP_SCHEMA)
    op.drop_index(
        "ix_app_copy_legacy_archive_owner_user_id",
        table_name="copy_legacy_archive",
        schema=APP_SCHEMA,
    )
    op.drop_table("copy_legacy_archive", schema=APP_SCHEMA)
