from fastapi.testclient import TestClient

from apps.api.main import create_app
from apps.api.routes import health as health_routes


def test_health_endpoint_returns_ok():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_endpoint_returns_readiness_report(monkeypatch):
    monkeypatch.setattr(
        health_routes,
        "build_readiness_report",
        lambda: {
            "status": "not_ready",
            "checks": {
                "tenants": {"ok": True, "game_ids": ["bg3", "blue_prince"]},
                "qdrant": {"ok": False, "error": "connection refused"},
            },
        },
    )
    client = TestClient(create_app())

    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["tenants"] == {"ok": True, "game_ids": ["bg3", "blue_prince"]}
    assert body["checks"]["qdrant"] == {"ok": False, "error": "connection refused"}
