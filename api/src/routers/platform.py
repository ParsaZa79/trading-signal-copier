"""Platform routes for paper copy-trading, providers, and trade events."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .. import platform_store
from ..security import get_current_user

router = APIRouter()
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


class ProviderRequest(BaseModel):
    name: str = Field(..., min_length=1)
    source_type: str = "manual"
    description: str = ""
    visibility: str = "public"


class RiskPolicyRequest(BaseModel):
    paper_trading: bool | None = None
    require_stop_loss: bool | None = None
    allowed_symbols: list[str] | str | None = None
    max_daily_loss: float | None = None
    max_open_trades: int | None = None
    default_fixed_lot: float | None = None


class SubscriptionRequest(BaseModel):
    provider_id: str
    copy_mode: str = "fixed_lot"
    fixed_lot: float | None = None
    multiplier: float | None = None
    paper_trading: bool = True
    status: str = "active"


class TradeEventRequest(BaseModel):
    provider_id: str
    action: str = "open"
    symbol: str
    side: str | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profits: list[float] | str | None = None
    volume: float | None = None
    source: str = "manual_dashboard"
    external_id: str | None = None


class StressTestRequest(BaseModel):
    provider_id: str
    count: int = Field(default=100, ge=1, le=500)


def _handle_domain_error(error: Exception) -> HTTPException:
    if isinstance(error, PermissionError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


@router.get("/overview")
async def overview(current_user: CurrentUser) -> dict[str, Any]:
    return platform_store.platform_overview(current_user["id"])


@router.get("/providers")
async def providers(current_user: CurrentUser) -> dict[str, Any]:
    return {"success": True, "providers": platform_store.list_providers(current_user["id"])}


@router.post("/providers")
async def create_provider(request: ProviderRequest, current_user: CurrentUser) -> dict[str, Any]:
    try:
        provider = platform_store.create_provider(current_user["id"], request.model_dump())
    except ValueError as error:
        raise _handle_domain_error(error) from error
    return {"success": True, "provider": provider}


@router.get("/risk-policy")
async def get_risk_policy(current_user: CurrentUser) -> dict[str, Any]:
    return {"success": True, "risk_policy": platform_store.get_risk_policy(current_user["id"])}


@router.put("/risk-policy")
async def save_risk_policy(
    request: RiskPolicyRequest, current_user: CurrentUser
) -> dict[str, Any]:
    try:
        policy = platform_store.upsert_risk_policy(
            current_user["id"], request.model_dump(exclude_unset=True)
        )
    except ValueError as error:
        raise _handle_domain_error(error) from error
    return {"success": True, "risk_policy": policy}


@router.get("/subscriptions")
async def subscriptions(current_user: CurrentUser) -> dict[str, Any]:
    return {
        "success": True,
        "subscriptions": platform_store.list_subscriptions(current_user["id"]),
    }


@router.post("/subscriptions")
async def create_subscription(
    request: SubscriptionRequest, current_user: CurrentUser
) -> dict[str, Any]:
    try:
        subscription = platform_store.create_subscription(current_user["id"], request.model_dump())
    except (ValueError, PermissionError) as error:
        raise _handle_domain_error(error) from error
    return {"success": True, "subscription": subscription}


@router.get("/trade-events")
async def trade_events(current_user: CurrentUser, provider_id: str | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "events": platform_store.list_trade_events(current_user["id"], provider_id=provider_id),
    }


@router.post("/trade-events")
async def create_trade_event(
    request: TradeEventRequest, current_user: CurrentUser
) -> dict[str, Any]:
    try:
        event = platform_store.create_trade_event(current_user["id"], request.model_dump())
    except (ValueError, PermissionError) as error:
        raise _handle_domain_error(error) from error
    return {"success": True, "event": event}


@router.post("/trade-events/{event_id}/process")
async def process_trade_event(event_id: str, current_user: CurrentUser) -> dict[str, Any]:
    event = next(
        (
            item
            for item in platform_store.list_trade_events(current_user["id"])
            if item["id"] == event_id
        ),
        None,
    )
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade event not found")
    try:
        result = platform_store.process_trade_event(event_id)
    except ValueError as error:
        raise _handle_domain_error(error) from error
    return {"success": True, "result": result}


@router.get("/executions")
async def executions(current_user: CurrentUser) -> dict[str, Any]:
    return {"success": True, "executions": platform_store.list_executions(current_user["id"])}


@router.post("/stress-test")
async def stress_test(request: StressTestRequest, current_user: CurrentUser) -> dict[str, Any]:
    provider = platform_store.get_provider(request.provider_id)
    if not provider or provider.get("owner_user_id") != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    try:
        result = platform_store.run_stress_test(
            current_user["id"], request.provider_id, count=request.count
        )
    except ValueError as error:
        raise _handle_domain_error(error) from error
    return {"success": True, "result": result}
