from fastapi import APIRouter, Request
from civicproof.domain.incidents import IncidentCategory, Priority, IncidentReport, TriageDecision
from civicproof.services.triage import assign_priority, weather_risk
import json
import logging
import time

logger = logging.getLogger('civicproof')
router = APIRouter(prefix="/incidents", tags=["incidents"])

@router.post("/triage", response_model=TriageDecision)
def triage_incident(report: IncidentReport, request: Request) -> TriageDecision:
    classifier = request.app.state.classifier
    weather_client = request.app.state.weather_client
    model_predict_start = time.perf_counter()
    try:
        pred = classifier.predict(report.complaint_type, report.descriptor)
    except Exception as error:
        model_predict_time = time.perf_counter() - model_predict_start
        logger.exception(
            json.dumps(
                {
                    'event': 'incident_triage_failed',
                    'status': 'error',
                    'model_version': classifier.model_name,
                    'error_type': type(error).__name__,
                    'predict_time_ms': round(model_predict_time * 1000, 2),
                    'source': report.source.value
                }
            )
        )
        raise
    model_predict_time = time.perf_counter() - model_predict_start
    pred_category = IncidentCategory(pred['category'])
    pred_priority = assign_priority(report, pred_category)
    pred_rationale = [
        f"The model classified this record into the {pred['category']} category, with {pred['confidence'] * 100:.2f}% confidence",
        f"The priority rules assigned {pred_priority.value} priority"
    ]
    requires_human_review = pred['requires_human_review'] or pred_priority == Priority.CRITICAL
    weather_lookup_start = time.perf_counter()
    weather_evidence = weather_client.get_active_alerts(report.latitude, report.longitude)
    weather_lookup_time = time.perf_counter() - weather_lookup_start
    pred_priority, weather_rationale = weather_risk(weather_evidence, pred_category, pred_priority)
    pred_rationale.extend(weather_rationale)
    if len(weather_rationale) > 0:
        requires_human_review = True
    decision = TriageDecision(
       category=pred_category,
       priority=pred_priority,
       confidence=pred['confidence'],
       rationale=pred_rationale,
       probabilities=pred['probabilities'],
       requires_human_review=requires_human_review,
       model_version=pred['model_name'],
       weather_evidence=weather_evidence
    )
    logger.info(
        json.dumps(
            {
                'event': 'incident_triage_completed',
                'status': 'success',
                'model_version': decision.model_version,
                'category': decision.category.value,
                'confidence': decision.confidence,
                'priority': decision.priority.value,
                'requires_human_review': decision.requires_human_review,
                'predict_time_ms': round(model_predict_time * 1000, 2),
                'weather_lookup_time_ms': round(weather_lookup_time * 1000, 2),
                'weather_status': weather_evidence.status.value,
                'weather_alert_count': len(weather_evidence.alerts),
                'weather_cache_hit': weather_evidence.cache_hit,
                'source': report.source.value
            }
        )
    )
    return decision
