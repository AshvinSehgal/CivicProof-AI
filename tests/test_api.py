import pytest
from fastapi.testclient import TestClient
from civicproof.main import app
from civicproof.domain.incidents import WeatherAlert, WeatherEvidence, WeatherStatus
import json
import logging

class FakeEmbeddingClassifier():
    model_name = 'bge-small-v1-final'
    def load_model(self):
        pass
    def predict(self, complaint_type, descriptor):
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

class MissingModelClassifier:
    def load_model(self):
        raise FileNotFoundError("model.joblib is missing")
class FailingPredictionClassifier:
    model_name = 'bge-small-v1-final'

    def load_model(self):
        pass

    def predict(self, complaint_type, descriptor):
        raise RuntimeError('Prediction failed')

class FakeWeatherClient:
    def __init__(self, base_url, user_agent, timeout_seconds):
        pass
    def get_active_alerts(self, latitude, longitude):
        return WeatherEvidence(
            status=WeatherStatus.AVAILABLE,
            alerts=[
                WeatherAlert(
                    alert_id='alert-001',
                    event='Flood Warning',
                    severity='Severe',
                    urgency='Immediate',
                    certainty='Likely',
                    headline='Flood Warning issued',
                    effective='2026-08-04T12:00:00Z',
                    expires='2026-08-04T18:00:00Z'
                )
            ]
        )
    def close(self):
        pass

class UnavailableWeatherClient:
    def __init__(self, base_url, user_agent, timeout_seconds):
        pass
    def get_active_alerts(self, latitude, longitude):
        return WeatherEvidence(
            status=WeatherStatus.UNAVAILABLE,
            error_type='timeout'
        )
    def close(self):
        pass

def test_health(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_triage_returns_explainable_embedding_prediction(monkeypatch, caplog) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    payload = {
        "source": "open311",
        "external_id": "test-001",
        "complaint_type": "Damaged Tree",
        "descriptor": "Entire Tree Has Fallen Down",
        "description": "A fallen tree is blocking the road",
        "latitude": 40.7128,
        "longitude": -74.006,
    }
    with caplog.at_level(logging.INFO, logger='civicproof'):
        with TestClient(app) as client:
            response = client.post("/v1/incidents/triage", json=payload)
    events = []
    for record in caplog.records:
        try:
            events.append(json.loads(record.message))
        except json.JSONDecodeError:
            pass
    triage_events = [
        event
        for event in events
        if event.get('event') == 'incident_triage_completed'
    ]
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
    assert decision['weather_evidence']['status'] == 'available'
    assert len(decision['weather_evidence']['alerts']) == 1
    assert decision['weather_evidence']['alerts'][0]['event'] == 'Flood Warning'
    assert len(triage_events) == 1
    event = triage_events[0]
    assert event['status'] == 'success'
    assert event['category'] == 'fallen_tree'
    assert event['priority'] == 'high'
    assert event['model_version'] == 'bge-small-v1-final'
    assert event['predict_time_ms'] >= 0
    assert event['weather_lookup_time_ms'] >= 0
    assert event['weather_status'] == 'available'
    assert event['weather_alert_count'] == 1
    all_logs = caplog.text
    assert payload['description'] not in all_logs
    assert payload['descriptor'] not in all_logs
    assert str(payload['latitude']) not in all_logs
    assert str(payload['longitude']) not in all_logs

def test_missing_model_prevents_startup(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', MissingModelClassifier)
    with pytest.raises(FileNotFoundError):
        with TestClient(app):
            pass

def test_classifier_loads_once(monkeypatch) -> None:
    load_count = {"value": 0}
    class CountingClassifier:
        model_name = 'bge-small-v1-final'
        def load_model(self):
            load_count["value"] += 1
        def predict(self, complaint_type, descriptor):
            return {
                "category": "pothole",
                "confidence": 0.9,
                "probabilities": {
                    "fallen_tree": 0.025,
                    "flooding": 0.025,
                    "pothole": 0.9,
                    "road_obstruction": 0.025,
                    "unknown": 0.025,
                },
                "requires_human_review": False,
                "model_name": "bge-small-v1-final",
                "threshold": 0.4,
            }
    monkeypatch.setattr("civicproof.main.EmbeddingClassifier", CountingClassifier)
    monkeypatch.setattr("civicproof.main.NWSWeatherClient", FakeWeatherClient)
    payload = {
            "source": "open311",
            "external_id": "test-001",
            "complaint_type": "Damaged Tree",
            "descriptor": "Entire Tree Has Fallen Down",
            "description": "A fallen tree is blocking the road",
            "latitude": 40.7128,
            "longitude": -74.006,
        }
    with TestClient(app) as client:
        first_response = client.post("/v1/incidents/triage", json=payload)
        second_response = client.post("/v1/incidents/triage", json=payload)
        third_response = client.post("/v1/incidents/triage", json=payload)
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert third_response.status_code == 200
    assert load_count["value"] == 1

def test_prediction_failure_is_logged(monkeypatch, caplog) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FailingPredictionClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    payload = {
                "source": "open311",
                "external_id": "test-001",
                "complaint_type": "Damaged Tree",
                "descriptor": "Entire Tree Has Fallen Down",
                "description": "A fallen tree is blocking the road",
                "latitude": 40.7128,
                "longitude": -74.006,
            }
    with caplog.at_level(logging.ERROR, logger='civicproof'):
        with TestClient(app) as client:
            with pytest.raises(RuntimeError):
                client.post('/v1/incidents/triage', json=payload)
    events = []
    for record in caplog.records:
        try:
            events.append(json.loads(record.message))
        except json.JSONDecodeError:
            pass
    event = events[0]
    assert event['event'] == 'incident_triage_failed'
    assert event['status'] == 'error'
    assert event['error_type'] == 'RuntimeError'
    assert event['model_version'] == 'bge-small-v1-final'
    assert event['predict_time_ms'] >= 0
    all_logs = caplog.text
    assert payload['description'] not in all_logs
    assert payload['descriptor'] not in all_logs
    assert str(payload['latitude']) not in all_logs
    assert str(payload['longitude']) not in all_logs

def test_weather_timeout_does_not_fail_triage(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', UnavailableWeatherClient)
    payload = {
        "source": "open311",
        "external_id": "test-001",
        "complaint_type": "Damaged Tree",
        "descriptor": "Entire Tree Has Fallen Down",
        "description": "A fallen tree is blocking the road",
        "latitude": 40.7128,
        "longitude": -74.006,
    }
    with TestClient(app) as client:
        response = client.post('/v1/incidents/triage', json=payload)
    assert response.status_code == 200
    decision = response.json()
    assert decision['category'] == 'fallen_tree'
    assert decision['priority'] == 'high'
    assert decision['weather_evidence']['status'] == 'unavailable'
    assert decision['weather_evidence']['alerts'] == []
    assert decision['weather_evidence']['error_type'] == 'timeout'

def test_weather_client_closes_once(monkeypatch) -> None:
    close_count = {"value": 0}
    class CountingWeatherClient:
        def __init__(self, base_url, user_agent, timeout_seconds):
            pass
        def close(self):
            close_count["value"] += 1
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', CountingWeatherClient)
    with TestClient(app) as client:
        response = client.get('/health')
    assert response.status_code == 200
    assert close_count["value"] == 1
