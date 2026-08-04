from civicproof.domain.incidents import IncidentCategory, IncidentReport, Priority
from civicproof.services.triage import assign_priority, BaselineTriageService


def test_unknown_report_abstains_with_low_confidence() -> None:
    report = IncidentReport(
        source="user",
        external_id="test-unknown",
        complaint_type="Noise - Neighborhood",
        descriptor="Something unusual is happening near the corner",
        description="Something unusual is happening near the corner",
        latitude=40.7128,
        longitude=-74.006,
    )
    decision = BaselineTriageService().triage(report)
    assert decision.category is IncidentCategory.UNKNOWN
    assert decision.priority is Priority.LOW
    assert decision.confidence < 0.5
    assert decision.requires_human_review is True


def test_baseline_recognizes_canonical_categories() -> None:
    cases = [
        ("Flooding", "Street flooding near a clogged catch basin", IncidentCategory.FLOODING),
        ("Fallen Tree", "Branch or limb has fallen down", IncidentCategory.FALLEN_TREE),
        ("Pothole", "Large pothole in the traffic lane", IncidentCategory.POTHOLE),
        ("Road Obstruction", "Construction debris is blocking street access", IncidentCategory.ROAD_OBSTRUCTION),
    ]
    service = BaselineTriageService()
    for index, (type, description, expected) in enumerate(cases):
        report = IncidentReport(
            source="operator",
            external_id=f"canonical-{index}",
            complaint_type=type,
            descriptor=description,
            description=description,
            latitude=40.7128,
            longitude=-74.006,
        )
        assert service.triage(report).category is expected


def test_sewer_only_report_is_not_classified_as_flooding() -> None:
    report = IncidentReport(
        source="open311",
        external_id="sewer-only",
        complaint_type="Sewer",
        descriptor="Sewer Maintenance: Catch Basin Clogged",
        description="Sewer Maintenance: Catch Basin Clogged",
        latitude=40.7128,
        longitude=-74.006,
    )
    assert BaselineTriageService().triage(report).category is IncidentCategory.UNKNOWN
    
def test_trapped_person_has_critical_priority() -> None:
    report = IncidentReport(
            source="open311",
            external_id="trapped-person",
            complaint_type="Person trapped",
            descriptor="Person stuck in a manhole",
            description="Person stuck in a manhole",
            latitude=40.7128,
            longitude=-74.006,
        )
    assert assign_priority(report, IncidentCategory.UNKNOWN) is Priority.CRITICAL

def test_road_completely_blocked_has_high_priority() -> None:
    report = IncidentReport(
            source="open311",
            external_id="road-completely-blocked",
            complaint_type="Road completely blocked",
            descriptor="The road is blocked by some fallen trees",
            description="The road is blocked by some fallen trees",
            latitude=40.7128,
            longitude=-74.006,
        )
    assert assign_priority(report, IncidentCategory.ROAD_OBSTRUCTION) is Priority.HIGH

def test_pothole_has_medium_priority() -> None:
    report = IncidentReport(
            source="open311",
            external_id="pothole",
            complaint_type="Pothole",
            descriptor="Pothole lid has fallen off",
            description="Pothole lid has fallen off",
            latitude=40.7128,
            longitude=-74.006,
        )
    assert assign_priority(report, IncidentCategory.POTHOLE) is Priority.MEDIUM

def test_unknown_report_has_low_priority() -> None:
    report = IncidentReport(
            source="open311",
            external_id="unknown",
            complaint_type="Noise - Neighborhood",
            descriptor="Loud music",
            description="Loud music from a neighboring apartment",
            latitude=40.7128,
            longitude=-74.006,
        )
    assert assign_priority(report, IncidentCategory.UNKNOWN) is Priority.LOW
    
def test_fallen_power_line_has_critical_priority() -> None:
    report = IncidentReport(
            source="open311",
            external_id="pothole",
            complaint_type="Road obstruction",
            descriptor="Downed power line, street completely blocked",
            description="Downed power line, street completely blocked",
            latitude=40.7128,
            longitude=-74.006,
        )
    assert assign_priority(report, IncidentCategory.ROAD_OBSTRUCTION) is Priority.CRITICAL