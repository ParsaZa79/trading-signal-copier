"""Dashboard access management backed by WorkOS identities and invitations."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..access_store import (
    ACCESS_ROLES,
    invite_member,
    list_members,
    remove_member,
    require_access_admin,
    update_member,
    validate_member_invitation,
    validate_member_removal,
)
from ..security import get_current_user, provision_current_user
from ..session_payload import build_session_payload
from ..workos_client import (
    delete_workos_user,
    revoke_workos_invitation,
    revoke_workos_user_sessions,
    send_workos_invitation,
    workos_management_enabled,
)

router = APIRouter()
current_user_dependency = Depends(get_current_user)


class InviteMemberRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    role: Literal["owner", "admin", "trader", "viewer"] = "trader"


class UpdateMemberRequest(BaseModel):
    role: Literal["owner", "admin", "trader", "viewer"] | None = None
    status: Literal["active", "disabled", "pending"] | None = None


@router.get("/me")
async def me(current_user: dict = current_user_dependency) -> dict:
    return build_session_payload(current_user)


@router.post("/session")
async def provision_session(
    current_user: dict = Depends(provision_current_user),
) -> dict:
    """Provision or link app access after a successful WorkOS authentication."""
    return build_session_payload(current_user)


@router.get("")
@router.get("/")
async def get_access_members(current_user: dict = current_user_dependency) -> dict:
    require_access_admin(current_user)
    return {
        "success": True,
        "members": list_members(),
        "roles": sorted(ACCESS_ROLES),
        "workos": {
            "enabled": workos_management_enabled(),
            "invitations_enabled": workos_management_enabled(),
        },
    }


@router.post("/members")
async def add_access_member(
    request: InviteMemberRequest,
    current_user: dict = current_user_dependency,
) -> dict:
    require_access_admin(current_user)

    invitation_id = None
    invitation_status = "not_sent"
    try:
        clean_email = validate_member_invitation(request.email, request.role)
        if workos_management_enabled():
            invitation = send_workos_invitation(
                clean_email,
                inviter_user_id=current_user.get("workos_user_id") or current_user["id"],
            )
            invitation_id = invitation.get("id")
            invitation_status = invitation.get("state") or "pending"

        member = invite_member(
            email=clean_email,
            role=request.role,
            invited_by=current_user["id"],
            invitation_id=invitation_id,
            invitation_status=invitation_status,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WorkOS invitation could not be sent",
        ) from error

    return {"success": True, "member": member, "members": list_members()}


@router.patch("/members/{member_id}")
async def patch_access_member(
    member_id: str,
    request: UpdateMemberRequest,
    current_user: dict = current_user_dependency,
) -> dict:
    require_access_admin(current_user)
    try:
        member = update_member(member_id, role=request.role, status_value=request.status)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    if request.status == "disabled" and member.get("workos_user_id"):
        try:
            revoke_workos_user_sessions(str(member["workos_user_id"]))
        except Exception:
            print("WorkOS session revocation failed after local access was disabled")
    return {"success": True, "member": member, "members": list_members()}


@router.delete("/members/{member_id}")
async def delete_access_member(
    member_id: str,
    current_user: dict = current_user_dependency,
) -> dict:
    require_access_admin(current_user)
    try:
        member = validate_member_removal(member_id)
        if workos_management_enabled():
            if member.get("workos_user_id"):
                delete_workos_user(str(member["workos_user_id"]))
            elif member.get("invitation_id"):
                revoke_workos_invitation(str(member["invitation_id"]))
        remove_member(member_id)
    except ValueError as error:
        error_status = (
            status.HTTP_404_NOT_FOUND
            if str(error) == "Member not found"
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=error_status, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="WorkOS user could not be removed",
        ) from error
    return {"success": True, "members": list_members()}
