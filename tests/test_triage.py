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
