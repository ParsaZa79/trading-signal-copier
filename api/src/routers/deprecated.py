"""One-release compatibility responses for removed signal-ingestion APIs."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter()

_REMOVED = ("telegram", "bot", "analysis", "platform", "prompts")


def _gone(area: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "code": "copy_marketplace_replaced_legacy_api",
            "message": (
                f"The {area} API was removed. Use the account-scoped /api/copy endpoints."
            ),
            "replacement": "/api/copy",
        },
    )


for _area in _REMOVED:

    @router.api_route(
        f"/{_area}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    async def removed_root(area: str = _area) -> None:
        _gone(area)

    @router.api_route(
        f"/{_area}/{{path:path}}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        include_in_schema=False,
    )
    async def removed_path(path: str, area: str = _area) -> None:
        del path
        _gone(area)
