from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func
from civicproof.db.models.incident import Incident

class IncidentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def upsert_incident(self, incident_data: dict) -> Incident:
        insert_statement = insert(Incident).values(**incident_data)
        upsert_statement = insert_statement.on_conflict_do_update(
            constraint='uq_incidents_source_external_id',
            set_ = {
                'complaint_type': insert_statement.excluded.complaint_type,
                'descriptor': insert_statement.excluded.descriptor,
                'description': insert_statement.excluded.description,
                'latitude': insert_statement.excluded.latitude,
                'longitude': insert_statement.excluded.longitude,
                'category': insert_statement.excluded.category,
                'source_created_at': insert_statement.excluded.source_created_at,
                'raw_payload': insert_statement.excluded.raw_payload,
                'updated_at': func.now()
            }
        ).returning(Incident)
        result = await self.session.execute(
            upsert_statement,
            execution_options={'populate_existing': True}
        )
        incident = result.scalar_one()
        return incident
    
    async def get_incident(self, source: str, external_id: str) -> Incident | None:
        select_incident_statement = select(Incident).where(
            Incident.source == source,
            Incident.external_id == external_id
        )
        result = await self.session.execute(select_incident_statement)
        incident = result.scalar_one_or_none()
        return incident
        