import hashlib
import json
import random
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MAPPING_PATH = PROJECT_ROOT / "complaint_mapping.json"
SOURCE_PATHS = [
    PROJECT_ROOT / "nyc311_sample.json",
    PROJECT_ROOT / "nyc311_tree_street_raw.json",
    PROJECT_ROOT / "nyc311_road_obstruction_raw.json",
    PROJECT_ROOT / "nyc311_flooding_diverse_raw.json",
]
CATEGORIES = ["pothole", "fallen_tree", "flooding", "road_obstruction", "unknown"]
SEED = 3_112_026
RECORDS_PER_CATEGORY = 400
TRAIN_PER_CATEGORY = 280
VALIDATION_PER_CATEGORY = 60


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, indent=2)
        file.write("\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(65_536), b""):
            digest.update(block)
    return digest.hexdigest()


def build_pair_mapping(mapping: dict) -> dict[tuple[str, str], str]:
    pairs = {}
    for category_definition in mapping["categories"]:
        category = category_definition["category"]
        for inclusion in category_definition["includes"]:
            for descriptor in inclusion["descriptors"]:
                pair = (inclusion["complaint_type"], descriptor)
                if pair in pairs:
                    raise ValueError(f"Duplicate mapping pair: {pair}")
                pairs[pair] = category
    return pairs


def created_at(record: dict) -> datetime:
    return datetime.fromisoformat(record["created_date"].replace("Z", "+00:00"))


def main() -> None:
    mapping = load_json(MAPPING_PATH)
    if not isinstance(mapping, dict):
        raise TypeError("Complaint mapping must be a JSON object")
    pair_mapping = build_pair_mapping(mapping)

    records_before_deduplication = 0
    records_by_key = {}
    for source_path in SOURCE_PATHS:
        source_records = load_json(source_path)
        if not isinstance(source_records, list):
            raise TypeError(f"Expected a JSON array in {source_path.name}")
        records_before_deduplication += len(source_records)
        for source_record in source_records:
            record = dict(source_record)
            record.pop("category", None)
            record["category"] = pair_mapping.get(
                (record.get("complaint_type", ""), record.get("descriptor", "")),
                mapping["fallback"]["category"],
            )
            records_by_key[record["unique_key"]] = record

    categorized_records = sorted(records_by_key.values(), key=lambda record: record["unique_key"])
    available_counts = Counter(record["category"] for record in categorized_records)
    insufficient = {
        category: available_counts[category]
        for category in CATEGORIES
        if available_counts[category] < RECORDS_PER_CATEGORY
    }
    if insufficient:
        raise ValueError(f"Not enough records to balance the dataset: {insufficient}")

    rng = random.Random(SEED)
    balanced_records = []
    for category in CATEGORIES:
        candidates = [record for record in categorized_records if record["category"] == category]
        balanced_records.extend(rng.sample(candidates, RECORDS_PER_CATEGORY))

    balanced_records.sort(key=lambda record: (record["category"], created_at(record)))
    train_records = []
    validation_records = []
    test_records = []
    for category in CATEGORIES:
        category_records = [record for record in balanced_records if record["category"] == category]
        train_records.extend(category_records[:TRAIN_PER_CATEGORY])
        validation_records.extend(
            category_records[TRAIN_PER_CATEGORY : TRAIN_PER_CATEGORY + VALIDATION_PER_CATEGORY]
        )
        test_records.extend(category_records[TRAIN_PER_CATEGORY + VALIDATION_PER_CATEGORY :])

    output_records = {
        "nyc311_categorized.json": categorized_records,
        "nyc311_dataset.json": balanced_records,
        "nyc311_balanced.json": balanced_records,
        "nyc311_train.json": train_records,
        "nyc311_validation.json": validation_records,
        "nyc311_test.json": test_records,
    }
    for filename, records in output_records.items():
        write_json(PROJECT_ROOT / filename, records)

    manifest = {
        "dataset": "NYC 311 balanced CivicProof dataset",
        "taxonomy": CATEGORIES,
        "mapping_version": mapping["version"],
        "mapping": {"file": MAPPING_PATH.name, "sha256": sha256(MAPPING_PATH)},
        "inputs": [
            {"file": path.name, "sha256": sha256(path), "records": len(load_json(path))}
            for path in SOURCE_PATHS
        ],
        "source_records_before_deduplication": records_before_deduplication,
        "source_records_after_deduplication": len(categorized_records),
        "duplicates_removed": records_before_deduplication - len(categorized_records),
        "available_category_counts": dict(sorted(available_counts.items())),
        "selection": {
            "seed": SEED,
            "records_per_category": RECORDS_PER_CATEGORY,
            "method": "Fixed-seed random sampling within each category",
        },
        "split": {
            "method": "Chronological within each category after balancing",
            "train_per_category": TRAIN_PER_CATEGORY,
            "validation_per_category": VALIDATION_PER_CATEGORY,
            "test_per_category": RECORDS_PER_CATEGORY
            - TRAIN_PER_CATEGORY
            - VALIDATION_PER_CATEGORY,
        },
        "outputs": [
            {"file": filename, "sha256": sha256(PROJECT_ROOT / filename)}
            for filename in output_records
        ],
    }
    write_json(PROJECT_ROOT / "nyc311_balanced_manifest.json", manifest)

    print(f"Categorized {len(categorized_records)} unique records")
    print(f"Available counts: {dict(sorted(available_counts.items()))}")
    print(f"Balanced dataset: {len(balanced_records)} records")
    print(
        f"Splits: train={len(train_records)}, validation={len(validation_records)}, "
        f"test={len(test_records)}"
    )


if __name__ == "__main__":
    main()
