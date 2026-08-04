from fastapi.testclient import TestClient
from unittest.mock import patch

with patch("civicproof.services.embedding_classifier.EmbeddingClassifier.load_model"):
    from civicproof.main import app
from civicproof.api.routes.incidents import classifier

def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_triage_returns_explainable_embedding_prediction(monkeypatch) -> None:
    def mock_predict(complaint_type, descriptor):
        return {
            "category": "fallen_tree",
            "confidence": 0.9,
            "probabilities": {
                "fallen_tree": 0.9,
                "flooding": 0.025,
                "pothole": 0.025,
                "road_obstruction": 0.025,
                "unknown": 0.025,
            },
            "requires_human_review": False,
            "model_name": "bge-small-v1-final",
            "threshold": 0.4,
        }
    monkeypatch.setattr(classifier, "predict", mock_predict)
    payload = {
        "source": "open311",
        "external_id": "test-001",
        "complaint_type": "Damaged Tree",
        "descriptor": "Entire Tree Has Fallen Down",
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
    assert decision['rationale'] == [
        f"The model classified this record into the {decision['category']} category, with {decision['confidence'] * 100:.2f}% confidence",
        f"The priority rules assigned {decision['priority']} priority"
    ]
    assert decision["requires_human_review"] is False
    assert decision["model_version"] == "bge-small-v1-final"
    assert isinstance(decision['probabilities'], dict)
