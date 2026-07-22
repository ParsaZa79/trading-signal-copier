"""Allow verified WorkOS identities to adopt legacy application profiles.

Revision ID: 0004_rebind_workos_identity
Revises: 0003_copy_marketplace
"""

from alembic import op

revision: str = "0004_rebind_workos_identity"
down_revision: str | None = "0003_copy_marketplace"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

APP_SCHEMA = "app"

IDENTITY_FOREIGN_KEYS = (
    (
        "account_memberships_user_id_fkey",
        "account_memberships",
        "user_id",
    ),
    (
        "legacy_identity_aliases_user_id_fkey",
        "legacy_identity_aliases",
        "user_id",
    ),
    (
        "copy_trader_profiles_owner_user_id_fkey",
        "copy_trader_profiles",
        "owner_user_id",
    ),
    (
        "copy_subscriptions_follower_user_id_fkey",
        "copy_subscriptions",
        "follower_user_id",
    ),
)


def _replace_identity_foreign_keys(*, cascade_updates: bool) -> None:
    for constraint_name, table_name, column_name in IDENTITY_FOREIGN_KEYS:
        op.drop_constraint(
            constraint_name,
            table_name,
            schema=APP_SCHEMA,
            type_="foreignkey",
        )
        op.create_foreign_key(
            constraint_name,
            table_name,
            "app_user_profiles",
            [column_name],
            ["auth_subject"],
            source_schema=APP_SCHEMA,
            referent_schema=APP_SCHEMA,
            ondelete="CASCADE",
            onupdate="CASCADE" if cascade_updates else None,
        )


def upgrade() -> None:
    _replace_identity_foreign_keys(cascade_updates=True)


def downgrade() -> None:
    _replace_identity_foreign_keys(cascade_updates=False)
