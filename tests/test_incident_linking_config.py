import pytest
from civicproof.core.incident_linking_config import AUTO_LINK_THRESHOLD, INCIDENT_LINKING_CONFIG_VERSION, LINKING_RULES, REVIEW_THRESHOLD, SEMANTIC_WEIGHT, SPATIAL_WEIGHT, TEMPORAL_WEIGHT

def test_incident_linking_v1_configuration():
    assert INCIDENT_LINKING_CONFIG_VERSION == 'v1'
    assert REVIEW_THRESHOLD < AUTO_LINK_THRESHOLD
    assert SPATIAL_WEIGHT + TEMPORAL_WEIGHT + SEMANTIC_WEIGHT == pytest.approx(1.0)
    assert set(LINKING_RULES) == {'pothole', 'fallen_tree', 'flooding', 'road_obstruction', 'unknown'}