from fastapi.testclient import TestClient

from naijaledger.api.app import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "naijaledger-engine"
    assert "version" in body


def test_health_includes_cors_for_vite_dev_origin() -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:5174"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5174"
