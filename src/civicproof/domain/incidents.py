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
    description: str = Field(min_length=3, max_length=5_000)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    media_urls: list[str] = Field(default_factory=list, max_length=10)
class TriageDecision(BaseModel):
    category: IncidentCategory
    priority: Priority
    confidence: float = Field(ge=0, le=1)
    rationale: list[str]
    requires_human_review: bool = True
    baseline_version: str = "rules-v2"
