from datetime import datetime, timezone
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from civicproof.core.config import get_settings
from civicproof.db.models.incident import Incident
from civicproof.repositories.incidents import IncidentRepository

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

def create_incident_data(source='open311', external_id='repository-test-001'):
    return {
        'source': source,
        'external_id': external_id,
        'complaint_type': 'Street Condition',
        'descriptor': 'Pothole',
        'description': 'Large pothole in the roadway',
        'latitude': 40.7128,
        'longitude': -74.006,
        'category': 'pothole',
        'source_created_at': datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc),
        'raw_payload': {
            'unique_key': external_id,
            'complaint_type': 'Street Condition'
        }
    }

@pytest.mark.asyncio
async def test_upserting_new_external_id_creates_new_row(database_session):
    repository = IncidentRepository(database_session)
    incident_data = create_incident_data()
    incident = await repository.upsert_incident(incident_data)
    stored_incident = await repository.get_incident(
        incident_data["source"],
        incident_data["external_id"]
    )
    assert incident.id is not None
    assert stored_incident is not None
    assert stored_incident.id == incident.id
    assert stored_incident.source == "open311"
    assert stored_incident.external_id == "repository-test-001"
    assert stored_incident.category == "pothole"
    assert stored_incident.raw_payload == incident_data["raw_payload"]
    assert stored_incident.ingested_at is not None
    assert stored_incident.updated_at is not None

@pytest.mark.asyncio
async def test_upserting_existing_external_id(database_session):
    repository = IncidentRepository(database_session)
    incident_data = create_incident_data()
    original_incident = await repository.upsert_incident(incident_data)
    original_id = original_incident.id
    original_ingested_at = original_incident.ingested_at
    updated_data = create_incident_data()
    updated_data['description'] = 'Pothole is now obstructing traffic'
    updated_data['category'] = 'road_obstruction'
    updated_data['raw_payload'] = {
        'unique_key': 'repository-test-001',
        'complaint_type': 'Street Condition',
        'updated': True
    }
    updated_incident = await repository.upsert_incident(updated_data)
    count_statement = select(func.count()).select_from(Incident).where(
        Incident.source == 'open311',
        Incident.external_id == 'repository-test-001'
    )
    result = await database_session.execute(count_statement)
    record_count = result.scalar_one()
    assert record_count == 1
    assert updated_incident.id == original_id
    assert updated_incident.description == "Pothole is now obstructing traffic"
    assert updated_incident.category == "road_obstruction"
    assert updated_incident.raw_payload == updated_data['raw_payload']
    assert updated_incident.ingested_at == original_ingested_at

@pytest.mark.asyncio 
async def test_upserting_existing_external_id_but_different_source_creates_new_row(database_session):
    repository = IncidentRepository(database_session)
    open311_data = create_incident_data(source='open311', external_id='shared-external-id')
    user_data = create_incident_data(source='user', external_id='shared-external-id')
    open311_incident = await repository.upsert_incident(open311_data)
    user_incident = await repository.upsert_incident(user_data)
    count_statement = select(func.count()).select_from(Incident).where(
        Incident.external_id == 'shared-external-id'
    )
    result = await database_session.execute(count_statement)
    record_count = result.scalar_one()
    assert record_count == 2
    assert open311_incident.id != user_incident.id
    assert open311_incident.source == 'open311'
    assert user_incident.source == 'user'

@pytest.mark.asyncio
async def test_get_incident_returns_None_for_unknown(database_session):
    repository = IncidentRepository(database_session)
    incident = await repository.get_incident(
        'open311',
        'does-not-exist'
    )
    assert incident is None