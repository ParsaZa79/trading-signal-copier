"""WorkOS User Management helpers for dashboard invitations and identities."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from workos import WorkOSClient


def workos_management_enabled() -> bool:
    return bool(os.getenv("WORKOS_API_KEY", "").strip()) and bool(
        os.getenv("WORKOS_CLIENT_ID", "").strip()
    )


@lru_cache(maxsize=4)
def _workos_client(api_key: str, client_id: str) -> WorkOSClient:
    return WorkOSClient(api_key=api_key, client_id=client_id)


def get_workos_client() -> WorkOSClient:
    api_key = os.getenv("WORKOS_API_KEY", "").strip()
    client_id = os.getenv("WORKOS_CLIENT_ID", "").strip()
    if not api_key or not client_id:
        raise RuntimeError("WorkOS user management is not configured")
    return _workos_client(api_key, client_id)


def send_workos_invitation(email: str, inviter_user_id: str | None = None) -> dict[str, Any]:
    invitation = get_workos_client().user_management.send_invitation(
        email=email,
        inviter_user_id=inviter_user_id,
    )
    state = getattr(invitation, "state", "pending")
    return {
        "id": invitation.id,
        "state": getattr(state, "value", state) or "pending",
    }


def revoke_workos_invitation(invitation_id: str) -> None:
    get_workos_client().user_management.revoke_invitation(invitation_id)


def delete_workos_user(user_id: str) -> None:
    get_workos_client().user_management.delete_user(user_id)


def revoke_workos_user_sessions(user_id: str) -> None:
    user_management = get_workos_client().user_management
    sessions = user_management.list_sessions(user_id)
    for session in sessions.auto_paging_iter():
        user_management.revoke_session(session_id=session.id)
