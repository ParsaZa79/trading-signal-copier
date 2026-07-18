from unittest.mock import MagicMock

import pytest

from src.routers import health


@pytest.mark.asyncio
async def test_public_health_reports_missing_database_without_exposing_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health, "database_engine", lambda: None)

    response = await health.health_check()

    assert response == {
        "status": "unhealthy",
        "api": {"status": "healthy"},
        "database": {"status": "unhealthy", "error": "not_configured"},
    }


@pytest.mark.asyncio
async def test_public_health_reports_database_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = MagicMock()
    monkeypatch.setattr(health, "database_engine", lambda: engine)

    async def healthy_database(_engine: object) -> dict[str, object]:
        assert _engine is engine
        return {"status": "healthy", "latency_ms": 1.25}

    monkeypatch.setattr(health, "check_database_health", healthy_database)

    response = await health.health_check()

    assert response == {
        "status": "healthy",
        "api": {"status": "healthy"},
        "database": {"status": "healthy", "latency_ms": 1.25},
    }


@pytest.mark.asyncio
async def test_readiness_uses_http_failure_until_database_is_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unhealthy() -> dict[str, object]:
        return {
            "status": "unhealthy",
            "api": {"status": "healthy"},
            "database": {"status": "unhealthy", "error": "connection_failed"},
        }

    monkeypatch.setattr(health, "health_check", unhealthy)

    response = await health.readiness_check()

    assert response.status_code == 503
    assert b'"connection_failed"' in response.body
