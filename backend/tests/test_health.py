from fastapi.testclient import TestClient

from backend.app import app


def test_health_reports_api_availability() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
