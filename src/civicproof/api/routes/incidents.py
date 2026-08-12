from datetime import timedelta
from fastapi import APIRouter, Request, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from civicproof.domain.incidents import IncidentCategory, Priority, IncidentReport, TriageDecision, IncidentRead, NearbyIncidentRead, ReportSource
from civicproof.services.triage import assign_priority, weather_risk
from civicproof.db.session import get_database_session
from civicproof.repositories.incidents import IncidentRepository
import json
import logging
from typing import Annotated
import time

logger = logging.getLogger('civicproof')
router = APIRouter(prefix="/incidents", tags=["incidents"])
async_session_dep = Annotated[AsyncSession, Depends(get_database_session)]

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

@router.get("/{source}/{external_id}/nearby", response_model=list[NearbyIncidentRead])
async def fetch_nearby_incidents(source: ReportSource, external_id: str, async_session: async_session_dep, radius_meters: float = Query(default=100.0, ge=1, le=5_000), hours: int = Query(default=24, ge=1, le=168), limit: int = Query(default=100, ge=1, le=100)):
    incident_repository = IncidentRepository(async_session)
    incident = await incident_repository.get_incident(source.value, external_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with source {source.value} and external_id {external_id} does not exist."
        )
    nearby_incidents = await incident_repository.find_nearby_incidents(
        latitude=incident.latitude,
        longitude=incident.longitude,
        radius_meters=radius_meters,
        since=incident.source_created_at - timedelta(hours=hours),
        until=incident.source_created_at + timedelta(hours=hours),
        category=incident.category,
        exclude_incident_id=incident.id,
        reference_embedding=incident.embedding,
        limit=limit
    )
    return [
        NearbyIncidentRead(
            **IncidentRead.model_validate(nearby_incident).model_dump(),
            distance_meters=distance_meters
        )
        for nearby_incident, distance_meters, semantic_similarity in nearby_incidents
    ]

@router.get("/{source}/{external_id}", response_model=IncidentRead)
async def fetch_incident(source: ReportSource, external_id: str, async_session: async_session_dep):
    incident_repository = IncidentRepository(async_session)
    incident = await incident_repository.get_incident(source.value, external_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Incident with source {source.value} and external_id {external_id} does not exist."
        )
    return IncidentRead(
        id=incident.id,
        source=incident.source,
        external_id=incident.external_id,
        complaint_type=incident.complaint_type,
        descriptor=incident.descriptor,
        description=incident.description,
        latitude=incident.latitude,
        longitude=incident.longitude,
        category=incident.category,
        source_created_at=incident.source_created_at,
        ingested_at=incident.ingested_at,
        updated_at=incident.updated_at
    )
