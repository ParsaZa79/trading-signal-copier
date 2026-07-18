"""Health check router."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..db.health import check_database_health
from ..db.runtime import database_engine
from ..dependencies import get_mt5_executor

router = APIRouter()


@router.get("/")
async def health_check() -> dict:
    """Return a public, secret-free API and PostgreSQL liveness result."""
    engine = database_engine()
    if engine is None:
        return {
            "status": "unhealthy",
            "api": {"status": "healthy"},
            "database": {"status": "unhealthy", "error": "not_configured"},
        }

    database = await check_database_health(engine)
    return {
        "status": "healthy" if database["status"] == "healthy" else "unhealthy",
        "api": {"status": "healthy"},
        "database": database,
    }


@router.get("/ready")
async def readiness_check() -> JSONResponse:
    """Return a failing HTTP status until PostgreSQL is reachable."""
    result = await health_check()
    return JSONResponse(
        content=result,
        status_code=200 if result["status"] == "healthy" else 503,
    )


@router.get("/mt5")
async def mt5_health_check(executor=Depends(get_mt5_executor)) -> dict:
    """Check authenticated account-specific MT5 connection health.

    Returns:
        dict: Health status including connection state and account info.
    """
    try:
        health = executor.health_check()
        return {
            "status": "healthy" if health.get("connected") else "unhealthy",
            "mt5": health,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "mt5": {
                "connected": False,
                "error": str(e),
            },
        }
