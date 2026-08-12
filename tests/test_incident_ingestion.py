from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest
from civicproof.services.incident_ingestion import IncidentIngestionService

class FakeIncident:
    def __init__(self, external_id, incident_id):
        self.external_id = external_id
        self.id = incident_id

class FakeIncidentRepository:
    def __init__(self):
        self.incident_data = None
        self.call_count = 0
    async def upsert_incident(self, incident_data):
        self.incident_data = incident_data
        self.call_count += 1
        return FakeIncident(incident_data['external_id'], 1)

class FakeEmbeddingClassifier:
    def __init__(self):
        self.complaint_type = None
        self.descriptor = None
    def predict(self, complaint_type, descriptor):
        self.complaint_type = complaint_type
        self.descriptor = descriptor
        return {
            'category': 'flooding'
        }

class FakeIngestionFailureRepository:
    def __init__(self):
        self.ingestion_failure_data = None
        self.call_count = 0
    async def create_ingestion_failure(self, ingestion_failure_data):
        self.ingestion_failure_data = ingestion_failure_data
        self.call_count += 1

def generate_payload():
    return {
        "unique_key": "69556026",
        "created_date": "2026-07-01T01:51:00.000",
        "closed_date": "2026-07-02T13:15:00.000",
        "agency": "DEP",
        "complaint_type": "Water System",
        "descriptor": "Hydrant Running Full (WA4)",
        "status": "Closed",
        "resolution_description": "The Department of Environmental Protection investigated this complaint and shut the running hydrant.",
        "borough": "BRONX",
        "incident_zip": "10452",
        "latitude": "40.831900200234024",
        "longitude": "-73.92856270428858",
        "category": "unknown"
    }

def test_normalize_record():
    repository = FakeIncidentRepository()
    classifier = FakeEmbeddingClassifier()
    service = IncidentIngestionService(repository, classifier, FakeIngestionFailureRepository())
    incident = generate_payload()
    normalized_incident = service.normalize_record(incident)
    expected_created_at_date = datetime.fromisoformat(incident['created_date'].replace("Z", "+00:00")).replace(tzinfo=ZoneInfo("America/New_York"))
    assert 'source' in normalized_incident
    assert normalized_incident['source'] == 'open311'
    assert 'external_id' in normalized_incident
    assert normalized_incident['external_id'] == incident['unique_key']
    assert 'complaint_type' in normalized_incident
    assert normalized_incident['complaint_type'] == incident['complaint_type']
    assert 'descriptor' in normalized_incident
    assert normalized_incident['descriptor'] == incident['descriptor']
    assert 'description' in normalized_incident
    assert normalized_incident['description'] == incident['descriptor']
    assert 'latitude' in normalized_incident
    assert normalized_incident['latitude'] == float(incident['latitude'])
    assert 'longitude' in normalized_incident
    assert normalized_incident['longitude'] == float(incident['longitude'])
    assert 'category' in normalized_incident
    assert normalized_incident['category'] == 'flooding'
    assert normalized_incident['category'] != incident['category']
    assert 'source_created_at' in normalized_incident
    assert normalized_incident['source_created_at'] == expected_created_at_date
    assert 'raw_payload' in normalized_incident
    assert isinstance(normalized_incident['raw_payload'], dict)
    assert normalized_incident['raw_payload'] == dict(incident)
    assert classifier.complaint_type == incident['complaint_type']
    assert classifier.descriptor == incident['descriptor']

def test_parse_coordinates():
    service = IncidentIngestionService(FakeIncidentRepository(), FakeEmbeddingClassifier(), FakeIngestionFailureRepository())
    incident = generate_payload()
    latitude, longitude = service.parse_coordinates(incident)
    assert isinstance(latitude, float)
    assert isinstance(longitude, float)
    incident['latitude'] = 'abc'
    incident['longitude'] = 'xyz'
    with pytest.raises(ValueError, match="latitude and longitude must be valid numbers"):
        latitude, longitude = service.parse_coordinates(incident)
    incident['latitude'] = "100.0"
    incident['longitude'] = "-73.92856270428858"
    with pytest.raises(ValueError, match="latitude is outside the valid range"):
        latitude, longitude = service.parse_coordinates(incident)
    incident['latitude'] = "40.831900200234024"
    incident['longitude'] = "-250.0"
    with pytest.raises(ValueError, match="longitude is outside the valid range"):
        latitude, longitude = service.parse_coordinates(incident)

def test_parse_coordinates_with_missing_and_null_values():
    service = IncidentIngestionService(FakeIncidentRepository(), FakeEmbeddingClassifier(), FakeIngestionFailureRepository())
    incident = generate_payload()
    del incident['latitude']
    with pytest.raises(ValueError, match="latitude and longitude must be valid numbers"):
        service.parse_coordinates(incident)
    incident = generate_payload()
    incident['longitude'] = None
    with pytest.raises(ValueError, match="latitude and longitude must be valid numbers"):
        service.parse_coordinates(incident)

def test_required_text():
    service = IncidentIngestionService(FakeIncidentRepository(), FakeEmbeddingClassifier(), FakeIngestionFailureRepository())
    incident = generate_payload()
    assert service.required_text(incident, 'complaint_type') == incident['complaint_type']
    incident['complaint_type'] = '   '
    with pytest.raises(ValueError, match="complaint_type must be a non-empty string"):
        service.required_text(incident, 'complaint_type')
    incident['complaint_type'] = None
    with pytest.raises(ValueError, match="complaint_type must be a non-empty string"):
        service.required_text(incident, 'complaint_type')

def test_parse_created_at():
    service = IncidentIngestionService(FakeIncidentRepository(), FakeEmbeddingClassifier(), FakeIngestionFailureRepository())
    parsed_created_at = service.parse_created_at('2026-07-01T01:51:00.000')
    assert parsed_created_at.tzinfo == ZoneInfo('America/New_York')
    utc_created_at = service.parse_created_at('2026-07-01T01:51:00.000Z')
    assert utc_created_at.tzinfo == timezone.utc
    with pytest.raises(ValueError, match="created_date must be a non-empty string"):
        service.parse_created_at('')

def test_normalize_record_uses_description_when_provided():
    service = IncidentIngestionService(FakeIncidentRepository(), FakeEmbeddingClassifier(), FakeIngestionFailureRepository())
    incident = generate_payload()
    incident['description'] = '  Water is flowing from the hydrant  '
    normalized_incident = service.normalize_record(incident)
    assert normalized_incident['description'] == 'Water is flowing from the hydrant'
    assert normalized_incident['description'] != incident['resolution_description']

def test_normalize_record_requires_unique_key():
    service = IncidentIngestionService(FakeIncidentRepository(), FakeEmbeddingClassifier(), FakeIngestionFailureRepository())
    incident = generate_payload()
    del incident['unique_key']
    with pytest.raises(ValueError, match="unique_key is required"):
        service.normalize_record(incident)

@pytest.mark.asyncio
async def test_ingest_record_upserts_normalized_incident():
    repository = FakeIncidentRepository()
    ingestion_failure_repository = FakeIngestionFailureRepository()
    service = IncidentIngestionService(repository, FakeEmbeddingClassifier(), ingestion_failure_repository)
    incident = generate_payload()
    result = await service.ingest_record(incident)
    assert result['status'] == 'upserted'
    assert result['external_id'] == incident['unique_key']
    assert result['incident_id'] == 1
    assert repository.call_count == 1
    assert repository.incident_data['external_id'] == incident['unique_key']
    assert repository.incident_data['category'] == 'flooding'
    assert ingestion_failure_repository.call_count == 0

@pytest.mark.asyncio
async def test_ingest_record_returns_failure_for_invalid_record():
    repository = FakeIncidentRepository()
    ingestion_failure_repository = FakeIngestionFailureRepository()
    service = IncidentIngestionService(repository, FakeEmbeddingClassifier(), ingestion_failure_repository)
    incident = generate_payload()
    incident['latitude'] = 'invalid'
    result = await service.ingest_record(incident)
    assert result['status'] == 'failed'
    assert result['external_id'] == incident['unique_key']
    assert result['error_type'] == 'ValueError'
    assert result['error_message'] == 'latitude and longitude must be valid numbers'
    assert repository.call_count == 0
    assert ingestion_failure_repository.call_count == 1
    assert ingestion_failure_repository.ingestion_failure_data['source'] == 'open311'
    assert ingestion_failure_repository.ingestion_failure_data['external_id'] == incident['unique_key']
    assert ingestion_failure_repository.ingestion_failure_data['stage'] == 'normalization'
    assert ingestion_failure_repository.ingestion_failure_data['error_type'] == 'ValueError'
    assert ingestion_failure_repository.ingestion_failure_data['error_message'] == 'latitude and longitude must be valid numbers'
    assert ingestion_failure_repository.ingestion_failure_data['raw_payload'] == incident

@pytest.mark.asyncio
async def test_ingest_record_returns_failure_for_non_dictionary_record():
    repository = FakeIncidentRepository()
    ingestion_failure_repository = FakeIngestionFailureRepository()
    service = IncidentIngestionService(repository, FakeEmbeddingClassifier(), ingestion_failure_repository)
    result = await service.ingest_record(None)
    assert result['status'] == 'failed'
    assert result['external_id'] is None
    assert result['error_type'] == 'TypeError'
    assert result['error_message'] == 'incident must be a dictionary'
    assert repository.call_count == 0
    assert ingestion_failure_repository.call_count == 1
    assert ingestion_failure_repository.ingestion_failure_data['source'] == 'open311'
    assert ingestion_failure_repository.ingestion_failure_data['external_id'] is None
    assert ingestion_failure_repository.ingestion_failure_data['stage'] == 'normalization'
    assert ingestion_failure_repository.ingestion_failure_data['error_type'] == 'TypeError'
    assert ingestion_failure_repository.ingestion_failure_data['error_message'] == 'incident must be a dictionary'
    assert ingestion_failure_repository.ingestion_failure_data['raw_payload'] is None
