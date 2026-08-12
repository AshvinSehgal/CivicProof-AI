import asyncio
import time
from datetime import datetime
from sqlalchemy import select
from civicproof.db.models.incident import Incident
from civicproof.db.session import async_session, close_database
from civicproof.repositories.incidents import IncidentRepository
from civicproof.repositories.incident_clusters import IncidentClusterRepository
from civicproof.services.embedding_classifier import EmbeddingClassifier
from civicproof.services.incident_linking import IncidentLinkingService

async def link_existing_incidents():
    classifier = EmbeddingClassifier()
    classifier.load_model()
    start_time = time.perf_counter()
    try:
        async with async_session() as session:
            select_incidents_statement = select(Incident).order_by(
                Incident.source_created_at,
                Incident.id
            )
            result = await session.execute(select_incidents_statement)
            incidents = result.scalars().all()
            batch_size = 100
            missing_embeddings = [
                incident
                for incident in incidents
                if incident.embedding is None
            ]
            for batch_start in range(0, len(missing_embeddings), batch_size):
                batch = missing_embeddings[batch_start:batch_start + batch_size]
                embeddings = classifier.encode_incidents([
                    (
                        incident.complaint_type,
                        incident.descriptor,
                        incident.description
                    )
                    for incident in batch
                ])
                for incident, embedding in zip(batch, embeddings):
                    incident.embedding = embedding
                await session.commit()
                print(f"Embedded {min(batch_start + batch_size, len(missing_embeddings))}/{len(missing_embeddings)} incidents")
            incident_repository = IncidentRepository(session)
            cluster_repository = IncidentClusterRepository(session)
            linking_service = IncidentLinkingService(
                incident_repository,
                cluster_repository
            )
            for incident_number, incident in enumerate(incidents, start=1):
                await linking_service.link_incident(incident)
                if incident_number % batch_size == 0:
                    await session.commit()
                    print(f"Linked {incident_number}/{len(incidents)} incidents")
            await session.commit()
            total_time = time.perf_counter() - start_time
            print(f"[{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}] Linked {len(incidents)} incidents in {total_time:.2f}s")
    finally:
        await close_database()

if __name__ == '__main__':
    asyncio.run(link_existing_incidents())
