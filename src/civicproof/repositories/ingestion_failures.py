from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from civicproof.db.models.ingestion_failure import IngestionFailure

class IngestionFailureRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
        
    async def create_ingestion_failure(self, ingestion_failure_data: dict) -> IngestionFailure:
        insert_statement = insert(IngestionFailure).values(**ingestion_failure_data).returning(IngestionFailure)
        result = await self.session.execute(insert_statement)
        ingestion_failure = result.scalar_one()
        return ingestion_failure
    
    async def get_ingestion_failure(self, failure_id: int) -> IngestionFailure | None:
        select_failure_statement = select(IngestionFailure).where(
            IngestionFailure.id == failure_id
        )
        result = await self.session.execute(select_failure_statement)
        ingestion_failure = result.scalar_one_or_none()
        return ingestion_failure