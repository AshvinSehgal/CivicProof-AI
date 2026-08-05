from enum import StrEnum
from pydantic import BaseModel, Field
class ReportSource(StrEnum):
    OPEN311 = "open311"
    USER = "user"
    OPERATOR = "operator"
class IncidentCategory(StrEnum):
    FLOODING = "flooding"
    FALLEN_TREE = "fallen_tree"
    POTHOLE = "pothole"
    ROAD_OBSTRUCTION = "road_obstruction"
    UNKNOWN = "unknown"
class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
class IncidentReport(BaseModel):
    source: ReportSource
    external_id: str = Field(min_length=1, max_length=200)
    complaint_type: str = Field(min_length=1, max_length=500)
    descriptor: str = Field(min_length=1, max_length=5_000)
    description: str = Field(min_length=3, max_length=5_000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    media_urls: list[str] = Field(default_factory=list, max_length=10)
class WeatherStatus(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"

class WeatherAlert(BaseModel):
    alert_id: str
    event: str | None = None
    severity: str | None = None
    urgency: str | None = None
    certainty: str | None = None
    headline: str | None = None
    effective: str | None = None
    expires: str | None = None

class WeatherEvidence(BaseModel):
    status: WeatherStatus
    alerts: list[WeatherAlert] = Field(default_factory=list)
    error_type: str | None = None
    cache_hit: bool = False

class TriageDecision(BaseModel):
    category: IncidentCategory
    priority: Priority
    confidence: float = Field(ge=0, le=1)
    rationale: list[str]
    probabilities: dict[str, float] = Field(default_factory=dict)
    requires_human_review: bool = True
    model_version: str = "rules-v2"
    weather_evidence: WeatherEvidence | None = None
