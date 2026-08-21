from datetime import timedelta
from civicproof.core.incident_linking_config import AUTO_LINK_THRESHOLD, INCIDENT_LINKING_CONFIG_VERSION, LINKING_RULES, REVIEW_THRESHOLD, SEMANTIC_WEIGHT, SPATIAL_WEIGHT, TEMPORAL_WEIGHT
from civicproof.db.models.incident import Incident
from civicproof.db.models.incident_cluster import IncidentCluster
from civicproof.repositories.incidents import IncidentRepository
from civicproof.repositories.incident_clusters import IncidentClusterRepository

class IncidentLinkingService:
    def __init__(self, incident_repository: IncidentRepository, cluster_repository: IncidentClusterRepository):
        self.incident_repository = incident_repository
        self.cluster_repository = cluster_repository

    def calculate_link_score(self, distance_meters: float, time_difference_seconds: float, radius_meters: float, time_window_seconds: float, semantic_similarity: float | None) -> tuple[float, dict]:
        spatial_score = max(0.0, 1.0 - distance_meters / radius_meters)
        temporal_score = max(0.0, 1.0 - time_difference_seconds / time_window_seconds)
        if semantic_similarity is None:
            non_semantic_weight = SPATIAL_WEIGHT + TEMPORAL_WEIGHT
            spatial_weight = SPATIAL_WEIGHT / non_semantic_weight
            temporal_weight = TEMPORAL_WEIGHT / non_semantic_weight
            link_score = spatial_score * spatial_weight + temporal_score * temporal_weight
        else:
            semantic_score = max(0.0, min(1.0, semantic_similarity))
            spatial_weight = SPATIAL_WEIGHT
            temporal_weight = TEMPORAL_WEIGHT
            link_score = spatial_score * SPATIAL_WEIGHT + temporal_score * TEMPORAL_WEIGHT + semantic_score * SEMANTIC_WEIGHT
        link_score = round(link_score, 6)
        if link_score >= AUTO_LINK_THRESHOLD:
            decision = 'auto_link'
        elif link_score >= REVIEW_THRESHOLD:
            decision = 'human_review'
        else:
            decision = 'no_link'
        link_reason = {
            'distance_meters': round(distance_meters, 2),
            'time_difference_seconds': round(time_difference_seconds, 2),
            'spatial_weight': spatial_weight,
            'spatial_score': round(spatial_score, 4),
            'temporal_weight': temporal_weight,
            'temporal_score': round(temporal_score, 4),
            'semantic_similarity': round(semantic_similarity, 4) if semantic_similarity is not None else None,
            'threshold': AUTO_LINK_THRESHOLD,
            'auto_link_threshold': AUTO_LINK_THRESHOLD,
            'review_threshold': REVIEW_THRESHOLD,
            'decision': decision,
            'config_version': INCIDENT_LINKING_CONFIG_VERSION
        }
        return link_score, link_reason

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
        if len(candidates) == 0:
            return await self.create_new_cluster(incident)
        candidate, distance_meters, link_score, link_reason = candidates[0]
        if link_reason['decision'] == 'no_link':
            return await self.create_new_cluster(incident)
        if link_reason['decision'] == 'human_review':
            return await self.create_new_cluster(
                incident,
                {
                    'reason': 'human_review',
                    'candidate_incident_id': candidate.id,
                    'candidate_link_score': link_score,
                    'candidate_link_reason': link_reason,
                    'config_version': INCIDENT_LINKING_CONFIG_VERSION
                }
            )
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

    async def create_new_cluster(self, incident: Incident, link_reason=None) -> IncidentCluster:
        cluster = await self.cluster_repository.create_cluster(incident)
        if link_reason is None:
            link_reason = {
                'reason': 'cluster_anchor',
                'threshold': AUTO_LINK_THRESHOLD,
                'auto_link_threshold': AUTO_LINK_THRESHOLD,
                'review_threshold': REVIEW_THRESHOLD,
                'config_version': INCIDENT_LINKING_CONFIG_VERSION
            }
        await self.cluster_repository.add_member(
            cluster.id,
            incident.id,
            0.0,
            1.0,
            link_reason
        )
        return await self.cluster_repository.refresh_cluster(cluster)
