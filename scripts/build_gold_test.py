import json
import random
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATEGORIZED_PATH = PROJECT_ROOT / "nyc311_categorized.json"
CANDIDATES_PATH = PROJECT_ROOT / "nyc311_gold_candidates_raw.json"
BALANCED_PATH = PROJECT_ROOT / "nyc311_dataset.json"
MAPPING_PATH = PROJECT_ROOT / "complaint_mapping.json"
GOLD_PATH = PROJECT_ROOT / "nyc311_gold_test.json"
MANIFEST_PATH = PROJECT_ROOT / "nyc311_gold_test_manifest.json"
SEED = 3_112_026
TARGET_PER_CATEGORY = 50
SEWER_UNKNOWN_TARGET = 20
CATEGORIES = ["pothole", "fallen_tree", "flooding", "road_obstruction", "unknown"]
SEWER_COMPLAINT_TYPES = {"Sewer", "Sewer Maintenance", "Water Drainage"}
TREE_OBSTRUCTION_CLAUSES = (
    "the fallen tree or branch is blocking the road",
    "tree debris is obstructing a traffic lane",
    "the fallen tree has made the street impassable",
    "the fallen branch is blocking an intersection",
    "the tree is preventing vehicles from passing",
)


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, indent=2)
        file.write("\n")


def build_pair_mapping(mapping: dict) -> dict[tuple[str, str], str]:
    return {
        (inclusion["complaint_type"], descriptor): category_definition["category"]
        for category_definition in mapping["categories"]
        for inclusion in category_definition["includes"]
        for descriptor in inclusion["descriptors"]
    }


def select_diverse(records: list[dict], target: int, rng: random.Random) -> list[dict]:
    groups = defaultdict(list)
    for record in records:
        groups[(record["complaint_type"], record["descriptor"])].append(record)
    for group in groups.values():
        rng.shuffle(group)

    group_keys = list(groups)
    rng.shuffle(group_keys)
    selected = []
    while len(selected) < target and group_keys:
        remaining_keys = []
        for key in group_keys:
            if len(selected) == target:
                break
            selected.append(groups[key].pop())
            if groups[key]:
                remaining_keys.append(key)
        group_keys = remaining_keys
    return selected


def main() -> None:
    mapping = load_json(MAPPING_PATH)
    categorized_records = load_json(CATEGORIZED_PATH)
    candidate_records = load_json(CANDIDATES_PATH)
    balanced_records = load_json(BALANCED_PATH)
    if not all(
        isinstance(value, expected_type)
        for value, expected_type in (
            (mapping, dict),
            (categorized_records, list),
            (candidate_records, list),
            (balanced_records, list),
        )
    ):
        raise TypeError("Unexpected JSON structure in a gold-set input")

    pair_mapping = build_pair_mapping(mapping)
    combined_by_key = {}
    for source_record in categorized_records + candidate_records:
        record = dict(source_record)
        record["category"] = pair_mapping.get(
            (record.get("complaint_type", ""), record.get("descriptor", "")),
            mapping["fallback"]["category"],
        )
        combined_by_key[record["unique_key"]] = record

    balanced_keys = {record["unique_key"] for record in balanced_records}
    eligible = [record for key, record in combined_by_key.items() if key not in balanced_keys]
    rng = random.Random(SEED)
    selected_by_category = {}
    for category in CATEGORIES[:-1]:
        category_candidates = [record for record in eligible if record["category"] == category]
        if category == "fallen_tree":
            category_candidates = [
                record
                for record in category_candidates
                if record["descriptor"]
                in {"Branch or Limb Has Fallen Down", "Entire Tree Has Fallen Down"}
            ]
        selected_by_category[category] = select_diverse(
            category_candidates,
            TARGET_PER_CATEGORY,
            rng,
        )

    unknown_records = [record for record in eligible if record["category"] == "unknown"]
    sewer_unknown = select_diverse(
        [
            record
            for record in unknown_records
            if record.get("complaint_type") in SEWER_COMPLAINT_TYPES
        ],
        SEWER_UNKNOWN_TARGET,
        rng,
    )
    other_unknown = select_diverse(
        [
            record
            for record in unknown_records
            if record.get("complaint_type") not in SEWER_COMPLAINT_TYPES
        ],
        TARGET_PER_CATEGORY - SEWER_UNKNOWN_TARGET,
        rng,
    )
    selected_by_category["unknown"] = sewer_unknown + other_unknown

    insufficient = {
        category: len(records)
        for category, records in selected_by_category.items()
        if len(records) != TARGET_PER_CATEGORY
    }
    if insufficient:
        raise ValueError(f"Insufficient independent gold candidates: {insufficient}")

    gold_records = []
    for category in CATEGORIES:
        for record_index, record in enumerate(selected_by_category[category]):
            gold_record = dict(record)
            if category == "fallen_tree":
                boundary = "fallen_tree_vs_road_obstruction"
                gold_record["evaluation_description"] = (
                    f"{record['complaint_type']}: {record['descriptor']}; "
                    f"{TREE_OBSTRUCTION_CLAUSES[record_index % len(TREE_OBSTRUCTION_CLAUSES)]}."
                )
                gold_record["scenario_provenance"] = (
                    "NYC 311 record with a synthetic obstruction clause added "
                    "for boundary evaluation"
                )
            elif category == "flooding":
                boundary = "explicit_flooding"
            elif category == "unknown" and record.get("complaint_type") in SEWER_COMPLAINT_TYPES:
                boundary = "sewer_only"
            elif category == "unknown":
                boundary = "out_of_scope_unknown"
            else:
                boundary = "canonical_category"
            gold_record["gold_boundary"] = boundary
            gold_records.append(gold_record)

    gold_records.sort(
        key=lambda record: (
            CATEGORIES.index(record["category"]),
            record["complaint_type"],
            record["descriptor"],
            record["created_date"],
            record["unique_key"],
        )
    )
    write_json(GOLD_PATH, gold_records)

    pair_counts = Counter(
        (record["category"], record["complaint_type"], record["descriptor"])
        for record in gold_records
    )
    boundary_counts = Counter(record["gold_boundary"] for record in gold_records)
    manifest = {
        "dataset": GOLD_PATH.name,
        "purpose": "Independent, multi-category manual gold-set review",
        "seed": SEED,
        "record_count": len(gold_records),
        "labels": dict(Counter(record["category"] for record in gold_records)),
        "boundaries": dict(sorted(boundary_counts.items())),
        "overlap_with_balanced_dataset": 0,
        "review_status": "pending_manual_review",
        "warning": "Do not report gold-set metrics until labels have been manually reviewed.",
        "pairs": [
            {
                "category": category,
                "complaint_type": complaint_type,
                "descriptor": descriptor,
                "count": count,
            }
            for (category, complaint_type, descriptor), count in sorted(pair_counts.items())
        ],
    }
    write_json(MANIFEST_PATH, manifest)

    print(f"Created {GOLD_PATH.name} with {len(gold_records)} records")
    print(f"Labels: {manifest['labels']}")
    print(f"Boundaries: {manifest['boundaries']}")
    print("Review status: pending_manual_review")


if __name__ == "__main__":
    main()
