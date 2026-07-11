"""Provider-neutral dashboard session payload."""

from __future__ import annotations

from typing import Any

from .account_store import get_preferred_account, get_user_setup_status, list_user_accounts
from .security import sanitize_user


def build_session_payload(user: dict[str, Any]) -> dict[str, Any]:
    account = get_preferred_account(user)
    setup_status = get_user_setup_status(user)
    return {
        "success": True,
        "user": sanitize_user(user),
        "accounts": list_user_accounts(user["id"]),
        "active_account_id": account["id"] if account else None,
        "setup_complete": setup_status["setup_complete"],
        "setup": setup_status,
    }
