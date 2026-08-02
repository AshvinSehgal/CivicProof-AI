from civicproof.domain.incidents import IncidentCategory, IncidentReport, Priority, TriageDecision


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
