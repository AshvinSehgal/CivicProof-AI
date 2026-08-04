from fastapi import APIRouter
from civicproof.domain.incidents import IncidentCategory, Priority, IncidentReport, TriageDecision
from civicproof.services.embedding_classifier import EmbeddingClassifier
from civicproof.services.triage import assign_priority

router = APIRouter(prefix="/incidents", tags=["incidents"])

classifier = EmbeddingClassifier()
classifier.load_model()

@router.post("/triage", response_model=TriageDecision)
def triage_incident(report: IncidentReport) -> TriageDecision:
    pred = classifier.predict(report.complaint_type, report.descriptor)
    pred_category = IncidentCategory(pred['category'])
    pred_priority = assign_priority(report, pred_category)
    pred_rationale = [
        f"The model classified this record into the {pred['category']} category, with {pred['confidence'] * 100:.2f}% confidence",
        f"The priority rules assigned {pred_priority.value} priority"
    ]
    requires_human_review = pred['requires_human_review'] or pred_priority == Priority.CRITICAL
    return TriageDecision(
       category=pred_category,
       priority=pred_priority,
       confidence=pred['confidence'],
       rationale=pred_rationale,
       probabilities=pred['probabilities'],
       requires_human_review=requires_human_review,
       model_version=pred['model_name']
    )
