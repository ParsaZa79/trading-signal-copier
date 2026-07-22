"""Application authorization records linked to WorkOS identities."""

from __future__ import annotations

import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from .runtime_data import DATA_DIR

ACCESS_PATH = DATA_DIR / "access.json"
LEGACY_USERS_PATH = DATA_DIR / "users.json"
ACCOUNTS_PATH = DATA_DIR / "accounts.json"

ACCESS_ROLES = {"owner", "admin", "trader", "viewer"}
ACCESS_STATUSES = {"active", "disabled", "pending"}
ACCESS_ADMIN_ROLES = {"owner", "admin"}
SELF_SERVICE_ROLE = "trader"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return data if isinstance(data, dict) else default


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _load_store() -> dict[str, Any]:
    store = _read_json(ACCESS_PATH, {"members": {}})
    if not isinstance(store.get("members"), dict):
        store["members"] = {}
    return store


def _save_store(store: dict[str, Any]) -> None:
    _write_json(ACCESS_PATH, store)


def _clean_email(email: str) -> str:
    return email.strip().lower()


def _sanitize_member(member: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": member["id"],
        "workos_user_id": member.get("workos_user_id"),
        "email": member["email"],
        "role": member.get("role", "trader"),
        "status": member.get("status", "active"),
        "active_account_id": member.get("active_account_id"),
        "invited_by": member.get("invited_by"),
        "invitation_id": member.get("invitation_id"),
        "invitation_status": member.get("invitation_status"),
        "created_at": member.get("created_at"),
        "updated_at": member.get("updated_at"),
        "last_seen_at": member.get("last_seen_at"),
    }


def _bootstrap_emails() -> set[str]:
    raw = os.getenv("ACCESS_BOOTSTRAP_EMAILS", "")
    return {_clean_email(item) for item in raw.split(",") if item.strip()}


def _access_error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _legacy_user_for_email(email: str) -> dict[str, Any] | None:
    store = _read_json(LEGACY_USERS_PATH, {"users": {}})
    for user in store.get("users", {}).values():
        if isinstance(user, dict) and user.get("email", "").lower() == email:
            return dict(user)
    return None


def _migrate_legacy_accounts(old_user_id: str, new_user_id: str) -> str | None:
    store = _read_json(ACCOUNTS_PATH, {"accounts": {}})
    changed = False
    for account in store.get("accounts", {}).values():
        if isinstance(account, dict) and account.get("user_id") == old_user_id:
            account["user_id"] = new_user_id
            account["updated_at"] = _utc_now()
            changed = True
    if changed:
        _write_json(ACCOUNTS_PATH, store)

    legacy_user = _read_json(LEGACY_USERS_PATH, {"users": {}}).get("users", {}).get(old_user_id)
    if isinstance(legacy_user, dict):
        active = legacy_user.get("active_account_id")
        return str(active) if active else None
    return None


def list_members() -> list[dict[str, Any]]:
    members = [_sanitize_member(member) for member in _load_store()["members"].values()]
    return sorted(members, key=lambda item: (item.get("created_at") or "", item["email"]))


def get_member(member_id: str) -> dict[str, Any] | None:
    member = _load_store()["members"].get(member_id)
    return _sanitize_member(member) if isinstance(member, dict) else None


def _member_by_email(store: dict[str, Any], email: str) -> dict[str, Any] | None:
    for member in store["members"].values():
        if isinstance(member, dict) and member.get("email", "").lower() == email:
            return member
    return None


def _member_by_workos_id(store: dict[str, Any], workos_user_id: str) -> dict[str, Any] | None:
    member = store["members"].get(workos_user_id)
    if isinstance(member, dict):
        return member
    for item in store["members"].values():
        if isinstance(item, dict) and item.get("workos_user_id") == workos_user_id:
            return item
    return None


def _owner_count(store: dict[str, Any], *, exclude_member_id: str | None = None) -> int:
    return sum(
        1
        for member_id, member in store["members"].items()
        if member_id != exclude_member_id
        and isinstance(member, dict)
        and member.get("role") == "owner"
        and member.get("status") == "active"
    )


def _create_member(
    store: dict[str, Any],
    *,
    member_id: str,
    email: str,
    role: str,
    status_value: str,
    workos_user_id: str | None = None,
    invited_by: str | None = None,
    invitation_id: str | None = None,
    invitation_status: str | None = None,
    active_account_id: str | None = None,
) -> dict[str, Any]:
    now = _utc_now()
    member = {
        "id": member_id,
        "workos_user_id": workos_user_id,
        "email": email,
        "role": role,
        "status": status_value,
        "active_account_id": active_account_id,
        "invited_by": invited_by,
        "invitation_id": invitation_id,
        "invitation_status": invitation_status,
        "created_at": now,
        "updated_at": now,
    }
    store["members"][member_id] = member
    return member


def resolve_workos_member(workos_user_id: str, email: str) -> dict[str, Any]:
    """Link a verified WorkOS identity to the matching local access record."""
    clean_id = workos_user_id.strip()
    clean_email = _clean_email(email)
    if not clean_id or not clean_email or "@" not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    store = _load_store()
    member = _member_by_workos_id(store, clean_id)
    if member is not None:
        if member.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_access_error(
                    "access_disabled",
                    "This dashboard account has been disabled.",
                ),
            )
        member["email"] = clean_email
        member["workos_user_id"] = clean_id
        member["last_seen_at"] = _utc_now()
        member["updated_at"] = _utc_now()
        _save_store(store)
        return _sanitize_member(member)

    invited = _member_by_email(store, clean_email)
    if invited is not None:
        if invited.get("status") == "disabled":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=_access_error(
                    "access_disabled",
                    "This dashboard account has been disabled.",
                ),
            )

        old_id = str(invited["id"])
        migrated_active_account_id = (
            _migrate_legacy_accounts(old_id, clean_id) if old_id != clean_id else None
        )
        invited["id"] = clean_id
        invited["workos_user_id"] = clean_id
        invited["email"] = clean_email
        invited["status"] = "active"
        invited["invitation_status"] = "accepted"
        invited["active_account_id"] = (
            invited.get("active_account_id") or migrated_active_account_id
        )
        invited["last_seen_at"] = _utc_now()
        invited["updated_at"] = _utc_now()
        if old_id != clean_id:
            store["members"].pop(old_id, None)
            store["members"][clean_id] = invited
        _save_store(store)
        return _sanitize_member(invited)

    allowed_bootstrap = _bootstrap_emails()
    legacy_user = _legacy_user_for_email(clean_email)
    has_active_owner = _owner_count(store) > 0

    legacy_active_account_id = (
        _migrate_legacy_accounts(str(legacy_user["id"]), clean_id)
        if legacy_user is not None
        else None
    )
    can_bootstrap_owner = not has_active_owner and (
        not allowed_bootstrap or clean_email in allowed_bootstrap
    )
    role = "owner" if can_bootstrap_owner else SELF_SERVICE_ROLE
    member = _create_member(
        store,
        member_id=clean_id,
        workos_user_id=clean_id,
        email=clean_email,
        role=role,
        status_value="active",
        active_account_id=legacy_active_account_id,
    )
    member["last_seen_at"] = _utc_now()
    _save_store(store)
    return _sanitize_member(member)


def resolve_workos_member_by_id(workos_user_id: str) -> dict[str, Any]:
    clean_id = workos_user_id.strip()
    if not clean_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    store = _load_store()
    member = _member_by_workos_id(store, clean_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_access_error(
                "access_not_provisioned",
                "Dashboard access has not been provisioned for this session.",
            ),
        )
    if member.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_access_error(
                "access_disabled",
                "This dashboard account has been disabled.",
            ),
        )
    return _sanitize_member(member)


def set_member_active_account_id(member_id: str, account_id: str | None) -> None:
    store = _load_store()
    member = store["members"].get(member_id)
    if not isinstance(member, dict):
        raise ValueError("Member not found")
    member["active_account_id"] = account_id
    member["updated_at"] = _utc_now()
    _save_store(store)


def require_access_admin(user: dict[str, Any]) -> None:
    if user.get("role") not in ACCESS_ADMIN_ROLES or user.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")


def invite_member(
    *,
    email: str,
    role: str,
    invited_by: str,
    invitation_id: str | None = None,
    invitation_status: str | None = None,
) -> dict[str, Any]:
    clean_email = validate_member_invitation(email, role)

    store = _load_store()
    member = _member_by_email(store, clean_email)
    if member is None:
        member = _create_member(
            store,
            member_id=f"pending_{secrets.token_urlsafe(10)}",
            email=clean_email,
            role=role,
            status_value="pending",
            invited_by=invited_by,
            invitation_id=invitation_id,
            invitation_status=invitation_status or "pending",
        )
    else:
        member["role"] = role
        member["status"] = "pending" if not member.get("workos_user_id") else "active"
        member["invited_by"] = invited_by
        member["invitation_id"] = invitation_id or member.get("invitation_id")
        member["invitation_status"] = invitation_status or member.get("invitation_status")
        member["updated_at"] = _utc_now()

    _save_store(store)
    return _sanitize_member(member)


def validate_member_invitation(email: str, role: str) -> str:
    clean_email = _clean_email(email)
    if not clean_email or "@" not in clean_email:
        raise ValueError("Enter a valid email address")
    if role not in ACCESS_ROLES:
        raise ValueError("Invalid role")
    return clean_email


def _is_last_active_owner(store: dict[str, Any], member_id: str) -> bool:
    member = store["members"].get(member_id)
    return (
        isinstance(member, dict)
        and member.get("role") == "owner"
        and _owner_count(store, exclude_member_id=member_id) == 0
    )


def update_member(
    member_id: str,
    *,
    role: str | None = None,
    status_value: str | None = None,
) -> dict[str, Any]:
    store = _load_store()
    member = store["members"].get(member_id)
    if not isinstance(member, dict):
        raise ValueError("Member not found")

    if role is not None:
        if role not in ACCESS_ROLES:
            raise ValueError("Invalid role")
        if role != "owner" and _is_last_active_owner(store, member_id):
            raise ValueError("At least one active owner is required")
        member["role"] = role

    if status_value is not None:
        if status_value not in ACCESS_STATUSES:
            raise ValueError("Invalid status")
        if status_value != "active" and _is_last_active_owner(store, member_id):
            raise ValueError("At least one active owner is required")
        member["status"] = status_value

    member["updated_at"] = _utc_now()
    _save_store(store)
    return _sanitize_member(member)


def remove_member(member_id: str) -> None:
    validate_member_removal(member_id)
    store = _load_store()
    store["members"].pop(member_id, None)
    _save_store(store)


def validate_member_removal(member_id: str) -> dict[str, Any]:
    store = _load_store()
    member = store["members"].get(member_id)
    if not isinstance(member, dict):
        raise ValueError("Member not found")
    if member.get("role") == "owner" and _owner_count(store, exclude_member_id=member_id) == 0:
        raise ValueError("At least one active owner is required")
    return _sanitize_member(member)
