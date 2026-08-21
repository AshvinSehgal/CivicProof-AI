from datetime import datetime, timezone
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from geoalchemy2.elements import WKTElement
from civicproof.core.config import get_settings
from civicproof.db.models.incident import Incident
from civicproof.repositories.incidents import IncidentRepository
from civicproof.repositories.incident_clusters import IncidentClusterRepository
from civicproof.services.incident_linking import IncidentLinkingService

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
        'location': WKTElement('POINT(-74.006 40.7128)', srid=4326),
        'embedding': None,
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

@pytest.mark.asyncio
async def test_find_nearby_incidents_uses_distance_time_and_category(database_session):
    repository = IncidentRepository(database_session)
    center_data = create_incident_data(external_id='nearby-center')
    nearby_data = create_incident_data(external_id='nearby-match')
    nearby_data['longitude'] = -74.0055
    nearby_data['location'] = WKTElement('POINT(-74.0055 40.7128)', srid=4326)
    different_category_data = create_incident_data(external_id='nearby-different-category')
    different_category_data['category'] = 'flooding'
    await repository.upsert_incident(center_data)
    nearby_incident = await repository.upsert_incident(nearby_data)
    await repository.upsert_incident(different_category_data)
    nearby_incidents = await repository.find_nearby_incidents(
        latitude=center_data['latitude'],
        longitude=center_data['longitude'],
        radius_meters=100,
        since=datetime(2026, 8, 8, 11, 0, tzinfo=timezone.utc),
        until=datetime(2026, 8, 8, 13, 0, tzinfo=timezone.utc),
        category='pothole',
        exclude_incident_id=(await repository.get_incident('open311', 'nearby-center')).id
    )
    assert len(nearby_incidents) == 1
    assert nearby_incidents[0][0].id == nearby_incident.id
    assert 0 < nearby_incidents[0][1] < 100
    assert nearby_incidents[0][2] is None

@pytest.mark.asyncio
async def test_linking_nearby_semantically_similar_incidents_creates_one_cluster(database_session):
    incident_repository = IncidentRepository(database_session)
    cluster_repository = IncidentClusterRepository(database_session)
    linking_service = IncidentLinkingService(incident_repository, cluster_repository)
    first_data = create_incident_data(external_id='cluster-first')
    first_data['embedding'] = [1.0] + [0.0] * 383
    first_incident = await incident_repository.upsert_incident(first_data)
    first_cluster = await linking_service.link_incident(first_incident)
    second_data = create_incident_data(external_id='cluster-second')
    second_data['longitude'] = -74.0058
    second_data['location'] = WKTElement('POINT(-74.0058 40.7128)', srid=4326)
    second_data['embedding'] = [1.0] + [0.0] * 383
    second_incident = await incident_repository.upsert_incident(second_data)
    second_cluster = await linking_service.link_incident(second_incident)
    cluster_details = await cluster_repository.get_cluster_details(first_cluster.id)
    assert second_cluster.id == first_cluster.id
    assert second_cluster.report_count == 2
    assert cluster_details is not None
    assert len(cluster_details['members']) == 2
    second_membership = await cluster_repository.get_membership(second_incident.id)
    assert second_membership is not None
    assert second_membership.link_score >= 0.7
    assert second_membership.link_reason['semantic_similarity'] == pytest.approx(1.0)
