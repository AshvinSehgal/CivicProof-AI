from fastapi.testclient import TestClient

from civicproof.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_triage_returns_explainable_baseline() -> None:
    payload = {
        "source": "open311",
        "external_id": "test-001",
        "description": "A fallen tree is blocking the road after the storm",
        "latitude": 42.3601,
        "longitude": -71.0589,
    }
    with TestClient(app) as client:
        response = client.post("/v1/incidents/triage", json=payload)
    assert response.status_code == 200
    decision = response.json()
    assert decision["category"] == "fallen_tree"
    assert decision["priority"] == "high"
    assert decision["requires_human_review"] is True
    assert decision["baseline_version"] == "rules-v2"
