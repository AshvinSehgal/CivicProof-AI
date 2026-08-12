from datetime import datetime
from geoalchemy2 import Geography
from sqlalchemy import cast, literal, select
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
                'location': insert_statement.excluded.location,
                'embedding': insert_statement.excluded.embedding,
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

    async def find_nearby_incidents(self, latitude: float, longitude: float, radius_meters: float, since: datetime, until: datetime | None = None, category: str | None = None, exclude_incident_id: int | None = None, reference_embedding: list[float] | None = None, limit: int = 100) -> list[tuple[Incident, float, float | None]]:
        input_location = cast(
            func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326),
            Geography(geometry_type='POINT', srid=4326)
        )
        distance_meters = func.ST_Distance(
            Incident.location,
            input_location
        ).label('distance_meters')
        semantic_similarity = literal(None).label('semantic_similarity')
        if reference_embedding is not None:
            semantic_similarity = (
                1 - Incident.embedding.cosine_distance(reference_embedding)
            ).label('semantic_similarity')
        select_nearby_statement = select(
            Incident,
            distance_meters,
            semantic_similarity
        ).where(
            func.ST_DWithin(Incident.location, input_location, radius_meters),
            Incident.source_created_at >= since
        )
        if until is not None:
            select_nearby_statement = select_nearby_statement.where(
                Incident.source_created_at <= until
            )
        if category is not None:
            select_nearby_statement = select_nearby_statement.where(
                Incident.category == category
            )
        if exclude_incident_id is not None:
            select_nearby_statement = select_nearby_statement.where(
                Incident.id != exclude_incident_id
            )
        select_nearby_statement = select_nearby_statement.order_by(
            distance_meters,
            Incident.source_created_at,
            Incident.id
        ).limit(limit)
        result = await self.session.execute(select_nearby_statement)
        return [
            (
                incident,
                float(distance),
                float(similarity) if similarity is not None else None
            )
            for incident, distance, similarity in result.all()
        ]
