import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool
from civicproof.core.config import get_settings
from civicproof.db.models.ingestion_failure import IngestionFailure
from civicproof.repositories.ingestion_failures import IngestionFailureRepository

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

def create_ingestion_failure_data(source='open311', external_id='repository-failure-001'):
    return {
        'source': source,
        'external_id': external_id,
        'stage': 'normalization',
        'error_type': 'ValueError',
        'error_message': 'latitude and longitude must be valid numbers',
        'raw_payload': {
            'unique_key': external_id,
            'latitude': 'invalid',
            'longitude': '-74.006'
        }
    }

@pytest.mark.asyncio
async def test_creating_ingestion_failure_creates_new_row(database_session):
    repository = IngestionFailureRepository(database_session)
    ingestion_failure_data = create_ingestion_failure_data()
    ingestion_failure = await repository.create_ingestion_failure(ingestion_failure_data)
    stored_ingestion_failure = await repository.get_ingestion_failure(
        ingestion_failure.id
    )
    assert ingestion_failure.id is not None
    assert stored_ingestion_failure is not None
    assert stored_ingestion_failure.id == ingestion_failure.id
    assert stored_ingestion_failure.source == 'open311'
    assert stored_ingestion_failure.external_id == 'repository-failure-001'
    assert stored_ingestion_failure.stage == 'normalization'
    assert stored_ingestion_failure.error_type == 'ValueError'
    assert stored_ingestion_failure.error_message == 'latitude and longitude must be valid numbers'
    assert stored_ingestion_failure.raw_payload == ingestion_failure_data['raw_payload']
    assert stored_ingestion_failure.failed_at is not None
    assert stored_ingestion_failure.resolved_at is None

@pytest.mark.asyncio
async def test_creating_ingestion_failure_accepts_null_external_id(database_session):
    repository = IngestionFailureRepository(database_session)
    ingestion_failure_data = create_ingestion_failure_data(external_id=None)
    ingestion_failure_data['raw_payload'] = None
    ingestion_failure = await repository.create_ingestion_failure(ingestion_failure_data)
    assert ingestion_failure.id is not None
    assert ingestion_failure.external_id is None
    assert ingestion_failure.raw_payload is None

@pytest.mark.asyncio
async def test_creating_same_ingestion_failure_creates_two_rows(database_session):
    repository = IngestionFailureRepository(database_session)
    ingestion_failure_data = create_ingestion_failure_data()
    first_ingestion_failure = await repository.create_ingestion_failure(ingestion_failure_data)
    second_ingestion_failure = await repository.create_ingestion_failure(ingestion_failure_data)
    count_statement = select(func.count()).select_from(IngestionFailure).where(
        IngestionFailure.source == 'open311',
        IngestionFailure.external_id == 'repository-failure-001'
    )
    result = await database_session.execute(count_statement)
    record_count = result.scalar_one()
    assert record_count == 2
    assert first_ingestion_failure.id != second_ingestion_failure.id

@pytest.mark.asyncio
async def test_get_ingestion_failure_returns_None_for_unknown(database_session):
    repository = IngestionFailureRepository(database_session)
    ingestion_failure = await repository.get_ingestion_failure(
        999999999
    )
    assert ingestion_failure is None
