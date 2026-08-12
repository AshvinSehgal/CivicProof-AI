import pytest
from fastapi.testclient import TestClient
from civicproof.main import app
from civicproof.domain.incidents import WeatherAlert, WeatherEvidence, WeatherStatus
import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

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

class FloodingEmbeddingClassifier:
    model_name = 'bge-small-v1-final'
    def load_model(self):
        pass
    def predict(self, complaint_type, descriptor):
        return {
            "category": "flooding",
            "confidence": 0.9,
            "probabilities": {
                "fallen_tree": 0.025,
                "flooding": 0.9,
                "pothole": 0.025,
                "road_obstruction": 0.025,
                "unknown": 0.025,
            },
            "requires_human_review": False,
            "model_name": "bge-small-v1-final",
            "threshold": 0.4,
        }

class FakeWeatherClient:
    def __init__(self, base_url, user_agent, timeout_seconds, cache_ttl_seconds):
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
    def __init__(self, base_url, user_agent, timeout_seconds, cache_ttl_seconds):
        pass
    def get_active_alerts(self, latitude, longitude):
        return WeatherEvidence(
            status=WeatherStatus.UNAVAILABLE,
            error_type='timeout'
        )
    def close(self):
        pass

def create_stored_incident(external_id='stored-001'):
    return SimpleNamespace(
        id=1,
        source='open311',
        external_id=external_id,
        complaint_type='Street Condition',
        descriptor='Pothole',
        description='Large pothole in the roadway',
        latitude=40.7128,
        longitude=-74.006,
        category='pothole',
        source_created_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        ingested_at=datetime(2026, 8, 11, 12, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 8, 11, 12, 1, tzinfo=timezone.utc),
        embedding=None
    )

class FakeIncidentRepository:
    def __init__(self, session):
        pass
    async def get_incident(self, source, external_id):
        if external_id == 'does-not-exist':
            return None
        return create_stored_incident(external_id)
    async def find_nearby_incidents(self, **search_values):
        nearby_incident = create_stored_incident('stored-nearby')
        nearby_incident.id = 2
        return [(nearby_incident, 42.5, None)]

class FakeIncidentClusterRepository:
    def __init__(self, session):
        pass
    async def get_cluster_details(self, cluster_id):
        if cluster_id == 404:
            return None
        cluster = SimpleNamespace(
            id=cluster_id,
            category='pothole',
            status='active',
            first_reported_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
            last_reported_at=datetime(2026, 8, 11, 12, 5, tzinfo=timezone.utc),
            report_count=1,
            created_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 11, 12, 5, tzinfo=timezone.utc)
        )
        member = SimpleNamespace(
            incident_id=1,
            distance_meters=0.0,
            link_score=1.0,
            link_reason={'reason': 'cluster_anchor'},
            linked_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
        )
        return {
            'cluster': cluster,
            'centroid_latitude': 40.7128,
            'centroid_longitude': -74.006,
            'members': [(member, create_stored_incident())]
        }

def test_health(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_fetch_incident_returns_stored_incident(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    monkeypatch.setattr('civicproof.api.routes.incidents.IncidentRepository', FakeIncidentRepository)
    with TestClient(app) as client:
        response = client.get('/v1/incidents/open311/stored-001')
    assert response.status_code == 200
    incident = response.json()
    assert incident['external_id'] == 'stored-001'
    assert incident['category'] == 'pothole'
    assert incident['source_created_at'] == '2026-08-11T12:00:00Z'

def test_fetch_incident_returns_404_for_unknown_external_id(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    monkeypatch.setattr('civicproof.api.routes.incidents.IncidentRepository', FakeIncidentRepository)
    with TestClient(app) as client:
        response = client.get('/v1/incidents/open311/does-not-exist')
    assert response.status_code == 404
    assert response.json()['detail'] == 'Incident with source open311 and external_id does-not-exist does not exist.'

def test_fetch_incident_rejects_invalid_source(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    with TestClient(app) as client:
        response = client.get('/v1/incidents/invalid/stored-001')
    assert response.status_code == 422

def test_fetch_nearby_incidents_returns_distance(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    monkeypatch.setattr('civicproof.api.routes.incidents.IncidentRepository', FakeIncidentRepository)
    with TestClient(app) as client:
        response = client.get('/v1/incidents/open311/stored-001/nearby?radius_meters=100&hours=24')
    assert response.status_code == 200
    incidents = response.json()
    assert len(incidents) == 1
    assert incidents[0]['external_id'] == 'stored-nearby'
    assert incidents[0]['distance_meters'] == 42.5

def test_fetch_cluster_returns_members_and_link_reason(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    monkeypatch.setattr('civicproof.api.routes.clusters.IncidentClusterRepository', FakeIncidentClusterRepository)
    with TestClient(app) as client:
        response = client.get('/v1/clusters/1')
    assert response.status_code == 200
    cluster = response.json()
    assert cluster['id'] == 1
    assert cluster['report_count'] == 1
    assert cluster['members'][0]['external_id'] == 'stored-001'
    assert cluster['members'][0]['link_reason']['reason'] == 'cluster_anchor'

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
    assert event['weather_cache_hit'] is False
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
        def __init__(self, base_url, user_agent, timeout_seconds, cache_ttl_seconds):
            pass
        def close(self):
            close_count["value"] += 1
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FakeEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', CountingWeatherClient)
    with TestClient(app) as client:
        response = client.get('/health')
    assert response.status_code == 200
    assert close_count["value"] == 1

def test_relevant_weather_raises_priority_and_requires_review(monkeypatch) -> None:
    monkeypatch.setattr('civicproof.main.EmbeddingClassifier', FloodingEmbeddingClassifier)
    monkeypatch.setattr('civicproof.main.NWSWeatherClient', FakeWeatherClient)
    payload = {
        "source": "open311",
        "external_id": "test-flooding",
        "complaint_type": "Sewer",
        "descriptor": "Street Flooding",
        "description": "Water reported on the street",
        "latitude": 40.7128,
        "longitude": -74.006,
    }
    with TestClient(app) as client:
        response = client.post('/v1/incidents/triage', json=payload)
    assert response.status_code == 200
    decision = response.json()
    assert decision['category'] == 'flooding'
    assert decision['priority'] == 'high'
    assert decision['requires_human_review'] is True
    assert decision['rationale'][-1] == 'Relevant Flood Warning increased priority from medium to high'
