"""Authentication and session routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field

from ..account_store import ensure_default_account, list_user_accounts
from ..security import (
    authenticate_credentials,
    create_token,
    create_user,
    get_current_user,
    has_users,
    sanitize_user,
)

router = APIRouter()


class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=12)


class AuthResponse(BaseModel):
    success: bool
    token: str
    user: dict
    accounts: list[dict]
    active_account_id: str


def _auth_response(user: dict, response: Response) -> AuthResponse:
    account = ensure_default_account(user)
    accounts = list_user_accounts(user["id"])
    token = create_token(user["id"])
    response.set_cookie(
        "sc_session",
        token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=7 * 24 * 60 * 60,
    )
    return AuthResponse(
        success=True,
        token=token,
        user=sanitize_user(user),
        accounts=accounts,
        active_account_id=account["id"],
    )


@router.get("/bootstrap")
async def bootstrap_status() -> dict:
    from ..clerk_client import clerk_enabled

    return {
        "setup_required": False if clerk_enabled() else not has_users(),
        "auth_provider": "clerk" if clerk_enabled() else "local",
    }


@router.post("/setup", response_model=AuthResponse)
async def setup_admin(request: AuthRequest, response: Response) -> AuthResponse:
    if has_users():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Setup is already complete")
    try:
        user = create_user(request.email, request.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _auth_response(user, response)


@router.post("/login", response_model=AuthResponse)
async def login(request: AuthRequest, response: Response) -> AuthResponse:
    user = authenticate_credentials(request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return _auth_response(user, response)


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)) -> dict:
    account = ensure_default_account(current_user)
    return {
        "success": True,
        "user": sanitize_user(current_user),
        "accounts": list_user_accounts(current_user["id"]),
        "active_account_id": account["id"],
    }


@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie("sc_session")
    return {"success": True}
