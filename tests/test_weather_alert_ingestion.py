from datetime import timezone
import pytest
from civicproof.services.weather_alert_ingestion import WeatherAlertIngestionService

class FakeWeatherAlert:
    def __init__(self, alert_id, weather_alert_id):
        self.alert_id = alert_id
        self.id = weather_alert_id

class FakeWeatherAlertRepository:
    def __init__(self):
        self.weather_alert_data = None
        self.call_count = 0
    async def upsert_weather_alert(self, weather_alert_data):
        self.weather_alert_data = weather_alert_data
        self.call_count += 1
        return FakeWeatherAlert(weather_alert_data['alert_id'], 1)

class FakeIngestionFailureRepository:
    def __init__(self):
        self.ingestion_failure_data = None
        self.call_count = 0
    async def create_ingestion_failure(self, ingestion_failure_data):
        self.ingestion_failure_data = ingestion_failure_data
        self.call_count += 1

def generate_payload():
    return {
        "id": "https://api.weather.gov/alerts/urn:oid:test-alert-001",
        "type": "Feature",
        "geometry": None,
        "properties": {
            "id": "urn:oid:test-alert-001",
            "areaDesc": "New York County",
            "sent": "2026-08-09T14:24:00-04:00",
            "effective": "2026-08-09T14:24:00-04:00",
            "onset": "2026-08-09T14:24:00-04:00",
            "expires": "2026-08-10T19:00:00-04:00",
            "ends": "2026-08-10T19:00:00-04:00",
            "status": "Actual",
            "messageType": "Alert",
            "category": "Met",
            "severity": "Moderate",
            "certainty": "Likely",
            "urgency": "Expected",
            "event": "Heat Advisory",
            "headline": "Heat Advisory issued for New York City",
            "description": "Heat index values up to 98.",
            "instruction": "Use air conditioning to stay cool.",
            "response": "Execute"
        }
    }

def test_normalize_record():
    repository = FakeWeatherAlertRepository()
    ingestion_failure_repository = FakeIngestionFailureRepository()
    service = WeatherAlertIngestionService(repository, ingestion_failure_repository)
    weather_alert = generate_payload()
    normalized_weather_alert = service.normalize_record(weather_alert)
    assert 'alert_id' in normalized_weather_alert
    assert normalized_weather_alert['alert_id'] == weather_alert['properties']['id']
    assert 'event' in normalized_weather_alert
    assert normalized_weather_alert['event'] == weather_alert['properties']['event']
    assert 'severity' in normalized_weather_alert
    assert normalized_weather_alert['severity'] == weather_alert['properties']['severity']
    assert 'urgency' in normalized_weather_alert
    assert normalized_weather_alert['urgency'] == weather_alert['properties']['urgency']
    assert 'certainty' in normalized_weather_alert
    assert normalized_weather_alert['certainty'] == weather_alert['properties']['certainty']
    assert 'headline' in normalized_weather_alert
    assert normalized_weather_alert['headline'] == weather_alert['properties']['headline']
    assert 'description' in normalized_weather_alert
    assert normalized_weather_alert['description'] == weather_alert['properties']['description']
    assert 'instruction' in normalized_weather_alert
    assert normalized_weather_alert['instruction'] == weather_alert['properties']['instruction']
    assert 'area_description' in normalized_weather_alert
    assert normalized_weather_alert['area_description'] == weather_alert['properties']['areaDesc']
    assert 'status' in normalized_weather_alert
    assert normalized_weather_alert['status'] == weather_alert['properties']['status']
    assert 'message_type' in normalized_weather_alert
    assert normalized_weather_alert['message_type'] == weather_alert['properties']['messageType']
    assert 'category' in normalized_weather_alert
    assert normalized_weather_alert['category'] == weather_alert['properties']['category']
    assert 'response' in normalized_weather_alert
    assert normalized_weather_alert['response'] == weather_alert['properties']['response']
    assert 'geometry' in normalized_weather_alert
    assert normalized_weather_alert['geometry'] is None
    assert 'raw_payload' in normalized_weather_alert
    assert isinstance(normalized_weather_alert['raw_payload'], dict)
    assert normalized_weather_alert['raw_payload'] == dict(weather_alert)

def test_parse_datetime():
    service = WeatherAlertIngestionService(FakeWeatherAlertRepository(), FakeIngestionFailureRepository())
    parsed_datetime = service.parse_datetime('2026-08-09T14:24:00-04:00', 'sent')
    assert parsed_datetime.utcoffset().total_seconds() == -14400
    utc_datetime = service.parse_datetime('2026-08-09T18:24:00Z', 'sent')
    assert utc_datetime.tzinfo == timezone.utc
    assert service.parse_datetime(None, 'sent') is None
    with pytest.raises(ValueError, match="sent must be a valid ISO-8601 datetime"):
        service.parse_datetime('invalid', 'sent')
    with pytest.raises(ValueError, match="sent must include a timezone"):
        service.parse_datetime('2026-08-09T18:24:00', 'sent')

def test_required_text():
    service = WeatherAlertIngestionService(FakeWeatherAlertRepository(), FakeIngestionFailureRepository())
    weather_alert = generate_payload()
    properties = weather_alert['properties']
    assert service.required_text(properties, 'event') == properties['event']
    properties['event'] = '   '
    with pytest.raises(ValueError, match="event must be a non-empty string"):
        service.required_text(properties, 'event')
    properties['event'] = None
    with pytest.raises(ValueError, match="event must be a non-empty string"):
        service.required_text(properties, 'event')

def test_optional_text():
    service = WeatherAlertIngestionService(FakeWeatherAlertRepository(), FakeIngestionFailureRepository())
    weather_alert = generate_payload()
    properties = weather_alert['properties']
    assert service.optional_text(properties, 'headline') == properties['headline']
    properties['headline'] = '   '
    assert service.optional_text(properties, 'headline') is None
    properties['headline'] = None
    assert service.optional_text(properties, 'headline') is None

def test_normalize_record_requires_alert_id():
    service = WeatherAlertIngestionService(FakeWeatherAlertRepository(), FakeIngestionFailureRepository())
    weather_alert = generate_payload()
    del weather_alert['properties']['id']
    del weather_alert['id']
    with pytest.raises(ValueError, match="alert id is required"):
        service.normalize_record(weather_alert)

def test_normalize_record_requires_properties():
    service = WeatherAlertIngestionService(FakeWeatherAlertRepository(), FakeIngestionFailureRepository())
    weather_alert = generate_payload()
    del weather_alert['properties']
    with pytest.raises(ValueError, match="weather alert properties must be a dictionary"):
        service.normalize_record(weather_alert)

def test_normalize_record_validates_geometry():
    service = WeatherAlertIngestionService(FakeWeatherAlertRepository(), FakeIngestionFailureRepository())
    weather_alert = generate_payload()
    weather_alert['geometry'] = 'invalid'
    with pytest.raises(ValueError, match="geometry must be a dictionary or null"):
        service.normalize_record(weather_alert)

@pytest.mark.asyncio
async def test_ingest_record_upserts_normalized_weather_alert():
    repository = FakeWeatherAlertRepository()
    ingestion_failure_repository = FakeIngestionFailureRepository()
    service = WeatherAlertIngestionService(repository, ingestion_failure_repository)
    weather_alert = generate_payload()
    result = await service.ingest_record(weather_alert)
    assert result['status'] == 'upserted'
    assert result['alert_id'] == weather_alert['properties']['id']
    assert result['weather_alert_id'] == 1
    assert repository.call_count == 1
    assert repository.weather_alert_data['alert_id'] == weather_alert['properties']['id']
    assert repository.weather_alert_data['event'] == weather_alert['properties']['event']
    assert ingestion_failure_repository.call_count == 0

@pytest.mark.asyncio
async def test_ingest_record_returns_failure_for_invalid_weather_alert():
    repository = FakeWeatherAlertRepository()
    ingestion_failure_repository = FakeIngestionFailureRepository()
    service = WeatherAlertIngestionService(repository, ingestion_failure_repository)
    weather_alert = generate_payload()
    weather_alert['properties']['event'] = None
    result = await service.ingest_record(weather_alert)
    assert result['status'] == 'failed'
    assert result['alert_id'] == weather_alert['properties']['id']
    assert result['error_type'] == 'ValueError'
    assert result['error_message'] == 'event must be a non-empty string'
    assert repository.call_count == 0
    assert ingestion_failure_repository.call_count == 1
    assert ingestion_failure_repository.ingestion_failure_data['source'] == 'nws'
    assert ingestion_failure_repository.ingestion_failure_data['external_id'] == weather_alert['properties']['id']
    assert ingestion_failure_repository.ingestion_failure_data['stage'] == 'normalization'
    assert ingestion_failure_repository.ingestion_failure_data['error_type'] == 'ValueError'
    assert ingestion_failure_repository.ingestion_failure_data['error_message'] == 'event must be a non-empty string'
    assert ingestion_failure_repository.ingestion_failure_data['raw_payload'] == weather_alert
