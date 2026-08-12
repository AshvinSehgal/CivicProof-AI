from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated
from civicproof.db.session import get_database_session
from civicproof.domain.incidents import IncidentClusterMemberRead, IncidentClusterRead
from civicproof.repositories.incident_clusters import IncidentClusterRepository

router = APIRouter(prefix='/clusters', tags=['clusters'])
async_session_dep = Annotated[AsyncSession, Depends(get_database_session)]

@router.get('/{cluster_id}', response_model=IncidentClusterRead)
async def fetch_cluster(cluster_id: int, async_session: async_session_dep):
    cluster_repository = IncidentClusterRepository(async_session)
    cluster_details = await cluster_repository.get_cluster_details(cluster_id)
    if cluster_details is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident cluster with id {cluster_id} does not exist."
        )
    cluster = cluster_details['cluster']
    members = [
        IncidentClusterMemberRead(
            incident_id=member.incident_id,
            source=incident.source,
            external_id=incident.external_id,
            distance_meters=member.distance_meters,
            link_score=member.link_score,
            link_reason=member.link_reason,
            linked_at=member.linked_at
        )
        for member, incident in cluster_details['members']
    ]
    return IncidentClusterRead(
        id=cluster.id,
        category=cluster.category,
        status=cluster.status,
        centroid_latitude=cluster_details['centroid_latitude'],
        centroid_longitude=cluster_details['centroid_longitude'],
        first_reported_at=cluster.first_reported_at,
        last_reported_at=cluster.last_reported_at,
        report_count=cluster.report_count,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
        members=members
    )
