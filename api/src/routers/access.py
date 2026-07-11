"""Access management routes backed by Clerk identity."""

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
)
from ..clerk_client import clerk_enabled, create_clerk_invitation
from ..security import get_current_user
from ..session_payload import build_session_payload

router = APIRouter()
current_user_dependency = Depends(get_current_user)


class InviteMemberRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    role: Literal["owner", "admin", "trader", "viewer"] = "trader"
    redirect_url: str | None = None


class UpdateMemberRequest(BaseModel):
    role: Literal["owner", "admin", "trader", "viewer"] | None = None
    status: Literal["active", "disabled", "pending"] | None = None


@router.get("/me")
async def me(current_user: dict = current_user_dependency) -> dict:
    return build_session_payload(current_user)


@router.get("")
@router.get("/")
async def get_access_members(current_user: dict = current_user_dependency) -> dict:
    require_access_admin(current_user)
    return {
        "success": True,
        "members": list_members(),
        "roles": sorted(ACCESS_ROLES),
        "clerk": {
            "enabled": clerk_enabled(),
            "invitations_enabled": clerk_enabled(),
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
        if clerk_enabled():
            invitation = create_clerk_invitation(
                request.email,
                request.role,
                redirect_url=request.redirect_url,
            )
            invitation_id = invitation.get("id")
            invitation_status = invitation.get("status") or "pending"

        member = invite_member(
            email=request.email,
            role=request.role,
            invited_by=current_user["id"],
            invitation_id=invitation_id,
            invitation_status=invitation_status,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error

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
    return {"success": True, "member": member, "members": list_members()}


@router.delete("/members/{member_id}")
async def delete_access_member(
    member_id: str,
    current_user: dict = current_user_dependency,
) -> dict:
    require_access_admin(current_user)
    try:
        remove_member(member_id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return {"success": True, "members": list_members()}
