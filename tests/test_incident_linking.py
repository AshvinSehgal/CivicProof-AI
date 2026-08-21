from datetime import datetime, timezone
from types import SimpleNamespace
import pytest
from civicproof.services.incident_linking import IncidentLinkingService

class FakeIncidentRepository:
    def __init__(self, nearby_incidents):
        self.nearby_incidents = nearby_incidents
        self.search_values = None
    async def find_nearby_incidents(self, **search_values):
        self.search_values = search_values
        return self.nearby_incidents

class FakeClusterRepository:
    def __init__(self):
        self.memberships = {}
        self.clusters = {}
        self.member_values = []
        self.next_cluster_id = 1
    async def get_membership(self, incident_id):
        return self.memberships.get(incident_id)
    async def get_cluster(self, cluster_id, for_update=False):
        return self.clusters.get(cluster_id)
    async def create_cluster(self, incident):
        cluster = SimpleNamespace(id=self.next_cluster_id, report_count=0)
        self.next_cluster_id += 1
        self.clusters[cluster.id] = cluster
        return cluster
    async def add_member(self, cluster_id, incident_id, distance_meters, link_score, link_reason):
        member = SimpleNamespace(cluster_id=cluster_id, incident_id=incident_id)
        self.memberships[incident_id] = member
        self.member_values.append({
            'cluster_id': cluster_id,
            'incident_id': incident_id,
            'distance_meters': distance_meters,
            'link_score': link_score,
            'link_reason': link_reason
        })
        return member
    async def refresh_cluster(self, cluster):
        cluster.report_count = len([
            member
            for member in self.member_values
            if member['cluster_id'] == cluster.id
        ])
        return cluster

def create_incident(incident_id, external_id, created_at=None):
    return SimpleNamespace(
        id=incident_id,
        source='open311',
        external_id=external_id,
        category='flooding',
        latitude=40.7128,
        longitude=-74.006,
        source_created_at=created_at or datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        embedding=None
    )

def test_calculate_link_score_records_explainable_components():
    service = IncidentLinkingService(FakeIncidentRepository([]), FakeClusterRepository())
    link_score, link_reason = service.calculate_link_score(
        distance_meters=30,
        time_difference_seconds=1800,
        radius_meters=100,
        time_window_seconds=3600,
        semantic_similarity=0.8
    )
    assert link_score == pytest.approx(0.65)
    assert link_reason['spatial_score'] == 0.7
    assert link_reason['temporal_score'] == 0.5
    assert link_reason['semantic_similarity'] == 0.8
    assert link_reason['threshold'] == 0.7
    assert link_reason['review_threshold'] == 0.65
    assert link_reason['decision'] == 'human_review'
    assert link_reason['config_version'] == 'v1'

def test_link_score_decision_boundaries():
    service = IncidentLinkingService(FakeIncidentRepository([]), FakeClusterRepository())
    auto_link_score, auto_link_reason = service.calculate_link_score(
        distance_meters=30,
        time_difference_seconds=30,
        radius_meters=100,
        time_window_seconds=100,
        semantic_similarity=0.70
    )
    review_score, review_reason = service.calculate_link_score(
        distance_meters=35,
        time_difference_seconds=35,
        radius_meters=100,
        time_window_seconds=100,
        semantic_similarity=0.65
    )
    no_link_score, no_link_reason = service.calculate_link_score(
        distance_meters=36,
        time_difference_seconds=36,
        radius_meters=100,
        time_window_seconds=100,
        semantic_similarity=0.64
    )
    assert auto_link_score == pytest.approx(0.70)
    assert auto_link_reason['decision'] == 'auto_link'
    assert review_score == pytest.approx(0.65)
    assert review_reason['decision'] == 'human_review'
    assert no_link_score == pytest.approx(0.64)
    assert no_link_reason['decision'] == 'no_link'

def test_semantic_similarity_missing():
    service = IncidentLinkingService(FakeIncidentRepository([]), FakeClusterRepository())
    link_score, link_reason = service.calculate_link_score(
        distance_meters=36,
        time_difference_seconds=36,
        radius_meters=100,
        time_window_seconds=100,
        semantic_similarity=None
    )
    assert link_score == pytest.approx(0.64)
    assert link_reason['spatial_weight'] == pytest.approx(0.6 / 0.9)
    assert link_reason['temporal_weight'] == pytest.approx(0.3 / 0.9)
    assert link_reason['semantic_similarity'] is None
    assert link_reason['decision'] == 'no_link'

@pytest.mark.asyncio
async def test_link_incident_creates_cluster_when_no_candidate_qualifies():
    cluster_repository = FakeClusterRepository()
    service = IncidentLinkingService(FakeIncidentRepository([]), cluster_repository)
    incident = create_incident(1, 'link-new-cluster')
    cluster = await service.link_incident(incident)
    anchor_reason = cluster_repository.member_values[0]['link_reason']
    assert cluster.id == 1
    assert cluster.report_count == 1
    assert cluster_repository.member_values[0]['incident_id'] == incident.id
    assert cluster_repository.member_values[0]['link_score'] == 1.0
    assert anchor_reason['reason'] == 'cluster_anchor'
    assert anchor_reason['auto_link_threshold'] == 0.70
    assert anchor_reason['review_threshold'] == 0.65
    assert anchor_reason['config_version'] == 'v1'

@pytest.mark.asyncio
async def test_link_incident_creates_new_cluster_when_candidate_score_is_below_review_threshold():
    candidate = create_incident(1, 'no-link-candidate')
    incident = create_incident(2, 'no-link-new', datetime(2026, 8, 12, 11, 0, tzinfo=timezone.utc))
    incident_repository = FakeIncidentRepository([(candidate, 250.0, 0.1)])
    cluster_repository = FakeClusterRepository()
    service = IncidentLinkingService(incident_repository, cluster_repository)
    candidate_cluster = await service.create_new_cluster(candidate)
    incident_cluster = await service.link_incident(incident)
    assert incident_cluster.id != candidate_cluster.id
    assert candidate_cluster.report_count == 1
    assert incident_cluster.report_count == 1
    assert cluster_repository.memberships[candidate.id].cluster_id == candidate_cluster.id
    assert cluster_repository.memberships[incident.id].cluster_id == incident_cluster.id
    assert cluster_repository.member_values[-1]['link_reason']['reason'] == 'cluster_anchor'
    assert cluster_repository.member_values[-1]['link_reason']['config_version'] == 'v1'

@pytest.mark.asyncio
async def test_link_incident_joins_best_matching_candidate_cluster():
    candidate = create_incident(1, 'link-candidate')
    incident = create_incident(2, 'link-new')
    incident_repository = FakeIncidentRepository([(candidate, 10.0, 0.95)])
    cluster_repository = FakeClusterRepository()
    service = IncidentLinkingService(incident_repository, cluster_repository)
    candidate_cluster = await service.create_new_cluster(candidate)
    cluster = await service.link_incident(incident)
    link_reason = cluster_repository.member_values[-1]['link_reason']
    assert cluster.id == candidate_cluster.id
    assert cluster.report_count == 2
    assert cluster_repository.member_values[-1]['incident_id'] == incident.id
    assert cluster_repository.member_values[-1]['link_score'] >= 0.7
    assert incident_repository.search_values['category'] == 'flooding'
    assert incident_repository.search_values['exclude_incident_id'] == incident.id
    assert link_reason['decision'] == 'auto_link'
    assert link_reason['auto_link_threshold'] == 0.70
    assert link_reason['review_threshold'] == 0.65
    assert link_reason['config_version'] == 'v1'

@pytest.mark.asyncio
async def test_link_incident_keeps_ambiguous_candidate_in_separate_cluster_for_review():
    candidate = create_incident(1, 'review-candidate')
    incident = create_incident(2, 'review-new', datetime(2026, 8, 11, 20, 24, tzinfo=timezone.utc))
    incident_repository = FakeIncidentRepository([(candidate, 90.0, 0.6)])
    cluster_repository = FakeClusterRepository()
    service = IncidentLinkingService(incident_repository, cluster_repository)
    candidate_cluster = await service.create_new_cluster(candidate)
    cluster = await service.link_incident(incident)
    review_reason = cluster_repository.member_values[-1]['link_reason']
    candidate_reason = review_reason['candidate_link_reason']
    assert cluster.id != candidate_cluster.id
    assert cluster.report_count == 1
    assert cluster_repository.member_values[-1]['link_reason']['reason'] == 'human_review'
    assert cluster_repository.member_values[-1]['link_reason']['candidate_incident_id'] == candidate.id
    assert cluster_repository.member_values[-1]['link_reason']['candidate_link_reason']['decision'] == 'human_review'
    assert review_reason['reason'] == 'human_review'
    assert review_reason['candidate_incident_id'] == candidate.id
    assert review_reason['candidate_link_score'] == pytest.approx(0.675)
    assert review_reason['config_version'] == 'v1'
    assert candidate_reason['decision'] == 'human_review'
    assert candidate_reason['auto_link_threshold'] == 0.70
    assert candidate_reason['review_threshold'] == 0.65
    assert candidate_reason['config_version'] == 'v1'