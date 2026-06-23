"""User-owned trading account routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..account_store import (
    create_account,
    ensure_default_account,
    list_user_accounts,
    set_user_active_account,
)
from ..security import get_current_user

router = APIRouter()


class CreateAccountRequest(BaseModel):
    name: str = Field(default="Trading Account", min_length=1, max_length=80)


@router.get("")
@router.get("/")
async def list_accounts(current_user: dict = Depends(get_current_user)) -> dict:
    active = ensure_default_account(current_user)
    return {
        "success": True,
        "accounts": list_user_accounts(current_user["id"]),
        "active_account_id": active["id"],
    }


@router.post("")
@router.post("/")
async def add_account(
    request: CreateAccountRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    account = create_account(current_user["id"], request.name)
    return {
        "success": True,
        "account": account,
        "accounts": list_user_accounts(current_user["id"]),
    }


@router.put("/{account_id}/active")
async def set_active_account(
    account_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    try:
        account = set_user_active_account(current_user["id"], account_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return {
        "success": True,
        "account": account,
        "active_account_id": account["id"],
        "accounts": list_user_accounts(current_user["id"]),
    }
