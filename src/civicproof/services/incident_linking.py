from datetime import timedelta
from civicproof.db.models.incident import Incident
from civicproof.db.models.incident_cluster import IncidentCluster
from civicproof.repositories.incidents import IncidentRepository
from civicproof.repositories.incident_clusters import IncidentClusterRepository

LINKING_RULES = {
    'pothole': {'radius_meters': 50.0, 'hours': 72},
    'fallen_tree': {'radius_meters': 100.0, 'hours': 48},
    'flooding': {'radius_meters': 300.0, 'hours': 24},
    'road_obstruction': {'radius_meters': 150.0, 'hours': 24},
    'unknown': {'radius_meters': 50.0, 'hours': 12}
}
LINK_SCORE_THRESHOLD = 0.55

class IncidentLinkingService:
    def __init__(self, incident_repository: IncidentRepository, cluster_repository: IncidentClusterRepository):
        self.incident_repository = incident_repository
        self.cluster_repository = cluster_repository

    def calculate_link_score(self, distance_meters: float, time_difference_seconds: float, radius_meters: float, time_window_seconds: float, semantic_similarity: float | None) -> tuple[float, dict]:
        spatial_score = max(0.0, 1.0 - distance_meters / radius_meters)
        temporal_score = max(0.0, 1.0 - time_difference_seconds / time_window_seconds)
        if semantic_similarity is None:
            link_score = spatial_score * 0.6 + temporal_score * 0.4
        else:
            semantic_score = max(0.0, min(1.0, semantic_similarity))
            link_score = spatial_score * 0.4 + temporal_score * 0.25 + semantic_score * 0.35
        link_reason = {
            'distance_meters': round(distance_meters, 2),
            'time_difference_seconds': round(time_difference_seconds, 2),
            'spatial_score': round(spatial_score, 4),
            'temporal_score': round(temporal_score, 4),
            'semantic_similarity': round(semantic_similarity, 4) if semantic_similarity is not None else None,
            'threshold': LINK_SCORE_THRESHOLD
        }
        return round(link_score, 6), link_reason

    async def link_incident(self, incident: Incident) -> IncidentCluster:
        existing_membership = await self.cluster_repository.get_membership(incident.id)
        if existing_membership is not None:
            existing_cluster = await self.cluster_repository.get_cluster(
                existing_membership.cluster_id
            )
            return existing_cluster
        linking_rule = LINKING_RULES[incident.category]
        time_window = timedelta(hours=linking_rule['hours'])
        nearby_incidents = await self.incident_repository.find_nearby_incidents(
            latitude=incident.latitude,
            longitude=incident.longitude,
            radius_meters=linking_rule['radius_meters'],
            since=incident.source_created_at - time_window,
            until=incident.source_created_at + time_window,
            category=incident.category,
            exclude_incident_id=incident.id,
            reference_embedding=incident.embedding,
            limit=100
        )
        candidates = []
        for candidate, distance_meters, semantic_similarity in nearby_incidents:
            time_difference_seconds = abs(
                (incident.source_created_at - candidate.source_created_at).total_seconds()
            )
            link_score, link_reason = self.calculate_link_score(
                distance_meters,
                time_difference_seconds,
                linking_rule['radius_meters'],
                time_window.total_seconds(),
                semantic_similarity
            )
            candidates.append((candidate, distance_meters, link_score, link_reason))
        candidates.sort(
            key=lambda candidate: (
                -candidate[2],
                candidate[1],
                candidate[0].source_created_at,
                candidate[0].id
            )
        )
        if len(candidates) == 0 or candidates[0][2] < LINK_SCORE_THRESHOLD:
            return await self.create_new_cluster(incident)
        candidate, distance_meters, link_score, link_reason = candidates[0]
        candidate_membership = await self.cluster_repository.get_membership(candidate.id)
        if candidate_membership is None:
            cluster = await self.create_new_cluster(candidate)
        else:
            cluster = await self.cluster_repository.get_cluster(
                candidate_membership.cluster_id,
                for_update=True
            )
        await self.cluster_repository.add_member(
            cluster.id,
            incident.id,
            distance_meters,
            link_score,
            link_reason
        )
        return await self.cluster_repository.refresh_cluster(cluster)

    async def create_new_cluster(self, incident: Incident) -> IncidentCluster:
        cluster = await self.cluster_repository.create_cluster(incident)
        await self.cluster_repository.add_member(
            cluster.id,
            incident.id,
            0.0,
            1.0,
            {
                'reason': 'cluster_anchor',
                'threshold': LINK_SCORE_THRESHOLD
            }
        )
        return await self.cluster_repository.refresh_cluster(cluster)
