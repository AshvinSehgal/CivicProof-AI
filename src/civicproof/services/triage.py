from civicproof.domain.incidents import IncidentCategory, IncidentReport, Priority, TriageDecision, WeatherEvidence, WeatherStatus
class BaselineTriageService:
    _category_terms: dict[IncidentCategory, tuple[str, ...]] = {
        IncidentCategory.FLOODING: (
            "flood",
            "standing water",
            "ponding",
            "manhole overflow",
            "sewer overflow",
        ),
        IncidentCategory.FALLEN_TREE: (
            "fallen tree",
            "tree down",
            "downed tree",
            "branch or limb has fallen",
            "entire tree has fallen",
            "branch cracked and will fall",
            "tree leaning/uprooted",
            "tree trunk split",
        ),
        IncidentCategory.POTHOLE: ("pothole", "road hole"),
        IncidentCategory.ROAD_OBSTRUCTION: (
            "blocked road",
            "blocking the road",
            "blocking street",
            "blocked - construction",
            "obstruction",
            "debris",
            "dumpster",
            "traffic sign or signal blocked",
        ),
    }
    _danger_terms = ("injury", "trapped", "power line", "cannot pass", "blocking the road")

    def triage(self, report: IncidentReport) -> TriageDecision:
        text = report.description.casefold()
        category = next(
            (
                candidate
                for candidate, terms in self._category_terms.items()
                if any(term in text for term in terms)
            ),
            IncidentCategory.UNKNOWN,
        )
        danger_matches = [term for term in self._danger_terms if term in text]
        if danger_matches:
            priority = Priority.HIGH
        elif category is IncidentCategory.UNKNOWN:
            priority = Priority.LOW
        else:
            priority = Priority.MEDIUM
        rationale = [f"Matched baseline category: {category.value}"]
        if danger_matches:
            rationale.append(f"Matched risk indicators: {', '.join(danger_matches)}")
        else:
            rationale.append("No explicit high-risk indicator matched")
        return TriageDecision(
            category=category,
            priority=priority,
            confidence=0.75 if category is not IncidentCategory.UNKNOWN else 0.35,
            rationale=rationale,
        )

_critical_terms = ('person trapped', 'people trapped', 'injury', 'injured', 'live power line', 'downed power line', 'gas leak', 'emergency vehicle cannot pass')
_high_impact_terms = ('road completely blocked', 'street completely blocked', 'road impassable', 'street impassable', 'cannot pass', 'blocking the road', 'blocking street', 'water entering building', 'water entering basement', 'rapidly rising water')

def assign_priority(report: IncidentReport, category: IncidentCategory) -> Priority:
    full_description = (report.complaint_type + ' : ' + report.descriptor + ' , ' + report.description).casefold()
    if any(phrase in full_description for phrase in _critical_terms):
        return Priority.CRITICAL
    elif any(phrase in full_description for phrase in _high_impact_terms):
        return Priority.HIGH
    elif category != 'unknown':
        return Priority.MEDIUM
    return Priority.LOW

def weather_risk(weather_evidence: WeatherEvidence, category: IncidentCategory, priority: Priority) -> tuple[Priority, list[str]]:
    if weather_evidence.status is WeatherStatus.UNAVAILABLE:
        return priority, []
    for alert in weather_evidence.alerts:
        if alert.event is None or alert.severity is None:
            continue
        event = alert.event.casefold()
        severity = alert.severity.casefold()
        if severity != 'severe' and severity != 'extreme':
            continue
        relevant_alert = False
        if category is IncidentCategory.FLOODING and event in ('flood warning', 'flash flood warning', 'coastal flood warning'):
            relevant_alert = True
        elif category is IncidentCategory.FALLEN_TREE and event in ('high wind warning', 'severe thunderstorm warning'):
            relevant_alert = True
        elif category is IncidentCategory.ROAD_OBSTRUCTION and event == 'severe thunderstorm warning':
            relevant_alert = True
        if relevant_alert is False:
            continue
        if priority is Priority.LOW:
            new_priority = Priority.MEDIUM
        elif priority is Priority.MEDIUM:
            new_priority = Priority.HIGH
        else:
            return priority, []
        rationale = [f"Relevant {alert.event} increased priority from {priority.value} to {new_priority.value}"]
        return new_priority, rationale
    return priority, []
