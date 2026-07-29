from fastapi import APIRouter
from civicproof.domain.incidents import IncidentReport, TriageDecision
from civicproof.services.triage import BaselineTriageService

router = APIRouter(prefix="/incidents", tags=["incidents"])

@router.post("/triage", response_model=TriageDecision)
async def triage_incident(report: IncidentReport) -> TriageDecision:
    return BaselineTriageService().triage(report)
