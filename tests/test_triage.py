from civicproof.domain.incidents import IncidentCategory, IncidentReport, Priority
from civicproof.services.triage import BaselineTriageService


def test_unknown_report_abstains_with_low_confidence() -> None:
    report = IncidentReport(
        source="user",
        external_id="test-unknown",
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
        ("Street flooding near a clogged catch basin", IncidentCategory.FLOODING),
        ("Branch or limb has fallen down", IncidentCategory.FALLEN_TREE),
        ("Large pothole in the traffic lane", IncidentCategory.POTHOLE),
        ("Construction debris is blocking street access", IncidentCategory.ROAD_OBSTRUCTION),
    ]
    service = BaselineTriageService()
    for index, (description, expected) in enumerate(cases):
        report = IncidentReport(
            source="operator",
            external_id=f"canonical-{index}",
            description=description,
            latitude=40.7128,
            longitude=-74.006,
        )
        assert service.triage(report).category is expected


def test_sewer_only_report_is_not_classified_as_flooding() -> None:
    report = IncidentReport(
        source="open311",
        external_id="sewer-only",
        description="Sewer Maintenance: Catch Basin Clogged",
        latitude=40.7128,
        longitude=-74.006,
    )

    assert BaselineTriageService().triage(report).category is IncidentCategory.UNKNOWN
