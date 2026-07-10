from __future__ import annotations

from fastapi.testclient import TestClient

from src import security
from src.main import app
from src.routers import mt5


def test_mt5_brokers_endpoint_validates_and_serializes_catalog(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(security, "USERS_PATH", tmp_path / "users.json")
    monkeypatch.setattr(security, "DEV_SECRET_PATH", tmp_path / ".dev_app_secret")
    user = security.create_user("owner@example.com", "correct horse battery")
    token = security.create_token(user["id"])
    monkeypatch.setattr(
        mt5,
        "list_broker_servers",
        lambda: [
            {"value": "Demo-Server", "label": "Demo Broker"},
            {"value": "Learned-Server", "label": "Learned Broker", "source": "learned"},
        ],
    )

    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as client:
        response = client.get("/api/mt5/brokers")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "brokers": [
            {"value": "Demo-Server", "label": "Demo Broker", "source": "seed"},
            {"value": "Learned-Server", "label": "Learned Broker", "source": "learned"},
        ],
    }
