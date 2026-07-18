"""Idempotently archive the retired JSON platform records as paper-only evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from ..models.copy import CopyLegacyArchive
from ..runtime_data import DATA_DIR

LEGACY_PLATFORM_PATH = DATA_DIR / "platform.json"
RECORD_COLLECTIONS = (
    "providers",
    "risk_policies",
    "subscriptions",
    "trade_events",
    "executions",
)


def _load_legacy_records(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _owner_id(record: dict[str, Any]) -> str | None:
    for key in ("owner_user_id", "follower_user_id", "user_id"):
        value = record.get(key)
        if value:
            return str(value)
    return None


async def archive_legacy_copy_store(session_factory: async_sessionmaker) -> int:
    """Import every legacy record once without creating an active or live object."""
    store = _load_legacy_records(LEGACY_PLATFORM_PATH)
    imported = 0
    async with session_factory() as session:
        for collection in RECORD_COLLECTIONS:
            records = store.get(collection)
            if not isinstance(records, dict):
                continue
            for legacy_id, raw_record in records.items():
                if not isinstance(raw_record, dict):
                    continue
                statement = (
                    insert(CopyLegacyArchive)
                    .values(
                        record_type=collection,
                        legacy_id=str(legacy_id),
                        owner_user_id=_owner_id(raw_record),
                        payload=raw_record,
                        paper_only=True,
                    )
                    .on_conflict_do_nothing(
                        constraint="uq_copy_legacy_archive_record"
                    )
                )
                result = await session.execute(statement)
                imported += max(result.rowcount or 0, 0)
        await session.commit()
    return imported
