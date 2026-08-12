from datetime import datetime, timezone
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from civicproof.core.config import get_settings
from civicproof.db.models.weather_alert import WeatherAlert
from civicproof.repositories.weather_alerts import WeatherAlertRepository

@pytest_asyncio.fixture
async def database_session():
    settings = get_settings()
    test_engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool
    )
    connection = await test_engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await test_engine.dispose()

def create_weather_alert_data(alert_id='repository-alert-001'):
    return {
        'alert_id': alert_id,
        'event': 'Flood Warning',
        'severity': 'Severe',
        'urgency': 'Immediate',
        'certainty': 'Likely',
        'headline': 'Flood Warning issued for New York City',
        'description': 'Flooding caused by excessive rainfall is expected.',
        'instruction': 'Avoid flooded roads and move to higher ground.',
        'area_description': 'New York County',
        'status': 'Actual',
        'message_type': 'Alert',
        'category': 'Met',
        'response': 'Avoid',
        'effective_at': datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc),
        'onset_at': datetime(2026, 8, 9, 12, 15, tzinfo=timezone.utc),
        'expires_at': datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc),
        'ends_at': datetime(2026, 8, 9, 18, 0, tzinfo=timezone.utc),
        'sent_at': datetime(2026, 8, 9, 11, 55, tzinfo=timezone.utc),
        'geometry': {
            'type': 'Polygon',
            'coordinates': [[
                [-74.02, 40.70],
                [-73.98, 40.70],
                [-73.98, 40.75],
                [-74.02, 40.70]
            ]]
        },
        'raw_payload': {
            'id': alert_id,
            'properties': {
                'event': 'Flood Warning'
            }
        }
    }

@pytest.mark.asyncio
async def test_upserting_new_alert_id_creates_new_row(database_session):
    repository = WeatherAlertRepository(database_session)
    weather_alert_data = create_weather_alert_data()
    weather_alert = await repository.upsert_weather_alert(weather_alert_data)
    stored_weather_alert = await repository.get_weather_alert(
        weather_alert_data['alert_id']
    )
    assert weather_alert.id is not None
    assert stored_weather_alert is not None
    assert stored_weather_alert.id == weather_alert.id
    assert stored_weather_alert.alert_id == 'repository-alert-001'
    assert stored_weather_alert.event == 'Flood Warning'
    assert stored_weather_alert.category == 'Met'
    assert stored_weather_alert.geometry == weather_alert_data['geometry']
    assert stored_weather_alert.raw_payload == weather_alert_data['raw_payload']
    assert stored_weather_alert.first_seen_at is not None
    assert stored_weather_alert.last_seen_at is not None
    assert stored_weather_alert.updated_at is not None

@pytest.mark.asyncio
async def test_upserting_existing_alert_id(database_session):
    repository = WeatherAlertRepository(database_session)
    weather_alert_data = create_weather_alert_data()
    original_weather_alert = await repository.upsert_weather_alert(weather_alert_data)
    original_id = original_weather_alert.id
    original_first_seen_at = original_weather_alert.first_seen_at
    updated_data = create_weather_alert_data()
    updated_data['severity'] = 'Extreme'
    updated_data['headline'] = 'Flood Warning upgraded for New York City'
    updated_data['raw_payload'] = {
        'id': 'repository-alert-001',
        'properties': {
            'event': 'Flood Warning',
            'updated': True
        }
    }
    updated_weather_alert = await repository.upsert_weather_alert(updated_data)
    count_statement = select(func.count()).select_from(WeatherAlert).where(
        WeatherAlert.alert_id == 'repository-alert-001'
    )
    result = await database_session.execute(count_statement)
    record_count = result.scalar_one()
    assert record_count == 1
    assert updated_weather_alert.id == original_id
    assert updated_weather_alert.severity == 'Extreme'
    assert updated_weather_alert.headline == 'Flood Warning upgraded for New York City'
    assert updated_weather_alert.raw_payload == updated_data['raw_payload']
    assert updated_weather_alert.first_seen_at == original_first_seen_at
    assert updated_weather_alert.last_seen_at is not None

@pytest.mark.asyncio
async def test_upserting_different_alert_id_creates_new_row(database_session):
    repository = WeatherAlertRepository(database_session)
    first_weather_alert_data = create_weather_alert_data(alert_id='repository-alert-001')
    second_weather_alert_data = create_weather_alert_data(alert_id='repository-alert-002')
    first_weather_alert = await repository.upsert_weather_alert(first_weather_alert_data)
    second_weather_alert = await repository.upsert_weather_alert(second_weather_alert_data)
    count_statement = select(func.count()).select_from(WeatherAlert).where(
        WeatherAlert.alert_id.in_(['repository-alert-001', 'repository-alert-002'])
    )
    result = await database_session.execute(count_statement)
    record_count = result.scalar_one()
    assert record_count == 2
    assert first_weather_alert.id != second_weather_alert.id
    assert first_weather_alert.alert_id == 'repository-alert-001'
    assert second_weather_alert.alert_id == 'repository-alert-002'

@pytest.mark.asyncio
async def test_get_weather_alert_returns_None_for_unknown(database_session):
    repository = WeatherAlertRepository(database_session)
    weather_alert = await repository.get_weather_alert(
        'does-not-exist'
    )
    assert weather_alert is None
