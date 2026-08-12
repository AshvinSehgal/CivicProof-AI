from geoalchemy2 import Geometry
from geoalchemy2.elements import WKTElement
from datetime import datetime, timezone
from sqlalchemy import cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from civicproof.db.models.incident import Incident
from civicproof.db.models.incident_cluster import IncidentCluster, IncidentClusterMember

class IncidentClusterRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_cluster(self, cluster_id: int, for_update: bool = False) -> IncidentCluster | None:
        select_cluster_statement = select(IncidentCluster).where(
            IncidentCluster.id == cluster_id
        )
        if for_update:
            select_cluster_statement = select_cluster_statement.with_for_update()
        result = await self.session.execute(select_cluster_statement)
        return result.scalar_one_or_none()

    async def get_membership(self, incident_id: int) -> IncidentClusterMember | None:
        select_membership_statement = select(IncidentClusterMember).where(
            IncidentClusterMember.incident_id == incident_id
        )
        result = await self.session.execute(select_membership_statement)
        return result.scalar_one_or_none()

    async def create_cluster(self, incident: Incident) -> IncidentCluster:
        cluster = IncidentCluster(
            category=incident.category,
            status='active',
            centroid=WKTElement(
                f"POINT({incident.longitude} {incident.latitude})",
                srid=4326
            ),
            first_reported_at=incident.source_created_at,
            last_reported_at=incident.source_created_at,
            report_count=0
        )
        self.session.add(cluster)
        await self.session.flush()
        return cluster

    async def add_member(self, cluster_id: int, incident_id: int, distance_meters: float, link_score: float, link_reason: dict) -> IncidentClusterMember:
        member = IncidentClusterMember(
            cluster_id=cluster_id,
            incident_id=incident_id,
            distance_meters=distance_meters,
            link_score=link_score,
            link_reason=link_reason
        )
        self.session.add(member)
        await self.session.flush()
        return member

    async def refresh_cluster(self, cluster: IncidentCluster) -> IncidentCluster:
        select_cluster_statistics_statement = select(
            func.avg(Incident.latitude),
            func.avg(Incident.longitude),
            func.min(Incident.source_created_at),
            func.max(Incident.source_created_at),
            func.count(Incident.id)
        ).join(
            IncidentClusterMember,
            IncidentClusterMember.incident_id == Incident.id
        ).where(
            IncidentClusterMember.cluster_id == cluster.id
        )
        result = await self.session.execute(select_cluster_statistics_statement)
        latitude, longitude, first_reported_at, last_reported_at, report_count = result.one()
        cluster.centroid = WKTElement(
            f"POINT({float(longitude)} {float(latitude)})",
            srid=4326
        )
        cluster.first_reported_at = first_reported_at
        cluster.last_reported_at = last_reported_at
        cluster.report_count = report_count
        cluster.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return cluster

    async def get_cluster_details(self, cluster_id: int) -> dict | None:
        centroid_geometry = cast(IncidentCluster.centroid, Geometry(geometry_type='POINT', srid=4326))
        select_cluster_statement = select(
            IncidentCluster,
            func.ST_Y(centroid_geometry).label('centroid_latitude'),
            func.ST_X(centroid_geometry).label('centroid_longitude')
        ).where(
            IncidentCluster.id == cluster_id
        )
        result = await self.session.execute(select_cluster_statement)
        cluster_row = result.one_or_none()
        if cluster_row is None:
            return None
        cluster, centroid_latitude, centroid_longitude = cluster_row
        select_members_statement = select(
            IncidentClusterMember,
            Incident
        ).join(
            Incident,
            Incident.id == IncidentClusterMember.incident_id
        ).where(
            IncidentClusterMember.cluster_id == cluster_id
        ).order_by(
            IncidentClusterMember.linked_at,
            IncidentClusterMember.incident_id
        )
        member_result = await self.session.execute(select_members_statement)
        return {
            'cluster': cluster,
            'centroid_latitude': float(centroid_latitude),
            'centroid_longitude': float(centroid_longitude),
            'members': member_result.all()
        }
