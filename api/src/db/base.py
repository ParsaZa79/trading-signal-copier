"""Declarative base for FastAPI-owned PostgreSQL tables."""

from collections.abc import Mapping
from typing import Literal

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

APP_SCHEMA = "app"
type AlembicParentName = Literal[
    "schema_name",
    "table_name",
    "schema_qualified_table_name",
]


def include_app_schema_name(
    name: str | None,
    object_type: str,
    parent_names: Mapping[AlembicParentName, str | None],
) -> bool:
    """Keep Alembic autogeneration away from authentication-owned schemas."""
    if object_type == "schema":
        return name == APP_SCHEMA
    if object_type == "table":
        return parent_names.get("schema_name") == APP_SCHEMA
    return True


class Base(DeclarativeBase):
    """Base class whose tables are isolated from authentication-owned tables."""

    metadata = MetaData(schema=APP_SCHEMA)
