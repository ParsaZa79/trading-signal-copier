"""Create the namespace for FastAPI-owned tables.

Revision ID: 0001_app_schema
Revises:
"""

from sqlalchemy.schema import CreateSchema, DropSchema

from alembic import op
from src.db.base import APP_SCHEMA

revision: str = "0001_app_schema"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Create only the schema owned by FastAPI migrations."""
    op.execute(CreateSchema(APP_SCHEMA))


def downgrade() -> None:
    """Remove the FastAPI-owned schema after later revisions remove their objects."""
    op.execute(DropSchema(APP_SCHEMA))
