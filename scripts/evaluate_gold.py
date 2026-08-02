import json
from collections import Counter, defaultdict
from pathlib import Path

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from civicproof.domain.incidents import IncidentCategory, IncidentReport, ReportSource
from civicproof.services.triage import BaselineTriageService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_PATH = PROJECT_ROOT / "nyc311_gold_test.json"
MANIFEST_PATH = PROJECT_ROOT / "nyc311_gold_test_manifest.json"
EVALUATION_DIR = PROJECT_ROOT / "artifacts" / "evaluation"
PREDICTIONS_PATH = EVALUATION_DIR / "gold_baseline_predictions.json"
METRICS_PATH = EVALUATION_DIR / "gold_baseline_metrics.json"
CATEGORIES = [category.value for category in IncidentCategory]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(value, file, indent=2)
        file.write("\n")


def main() -> None:
    data = load_json(GOLD_PATH)
    manifest = load_json(MANIFEST_PATH)
    if not isinstance(data, list) or not isinstance(manifest, dict):
        raise TypeError("Unexpected gold-set JSON structure")
    if manifest.get("review_status") != "approved":
        raise RuntimeError("Gold-set evaluation requires an approved manifest")

    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    triage_service = BaselineTriageService()
    prediction_records = []
    actual_categories = []
    predicted_categories = []
    predictions_by_boundary = defaultdict(list)

    for record in data:
        input_description = record.get("evaluation_description") or (
            f"{record['complaint_type']}: {record['descriptor']}"
        )
        report = IncidentReport(
            source=ReportSource.OPEN311,
            external_id=record["unique_key"],
            description=input_description,
            latitude=float(record["latitude"]),
            longitude=float(record["longitude"]),
            media_urls=[],
        )
        decision = triage_service.triage(report)
        predicted = decision.category.value
        actual = IncidentCategory(record["category"]).value
        boundary = record["gold_boundary"]
        correct = actual == predicted

        actual_categories.append(actual)
        predicted_categories.append(predicted)
        predictions_by_boundary[boundary].append((actual, predicted))
        prediction_records.append(
            {
                "unique_key": record["unique_key"],
                "complaint_type": record["complaint_type"],
                "descriptor": record["descriptor"],
                "gold_boundary": boundary,
                "input_description": input_description,
                "used_evaluation_description": "evaluation_description" in record,
                "category": {
                    "actual": actual,
                    "predicted": predicted,
                    "correct": correct,
                },
            }
        )

    precision, recall, f1, support = precision_recall_fscore_support(
        actual_categories,
        predicted_categories,
        labels=CATEGORIES,
        average=None,
        zero_division=0,
    )
    matrix = confusion_matrix(actual_categories, predicted_categories, labels=CATEGORIES)
    total_records = len(actual_categories)
    per_category = {}
    for index, category in enumerate(CATEGORIES):
        true_positive = int(matrix[index, index])
        false_positive = int(matrix[:, index].sum() - true_positive)
        false_negative = int(matrix[index, :].sum() - true_positive)
        true_negative = total_records - true_positive - false_positive - false_negative
        per_category[category] = {
            "support": int(support[index]),
            "true_positive": true_positive,
            "false_positive": false_positive,
            "true_negative": true_negative,
            "false_negative": false_negative,
            "precision": float(precision[index]),
            "recall": float(recall[index]),
            "f1_score": float(f1[index]),
        }

    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        actual_categories,
        predicted_categories,
        labels=CATEGORIES,
        average="macro",
        zero_division=0,
    )
    per_boundary = {}
    for boundary, boundary_predictions in sorted(predictions_by_boundary.items()):
        actual = [pair[0] for pair in boundary_predictions]
        predicted = [pair[1] for pair in boundary_predictions]
        correct = sum(
            actual_value == predicted_value
            for actual_value, predicted_value in zip(actual, predicted, strict=True)
        )
        per_boundary[boundary] = {
            "record_count": len(boundary_predictions),
            "correct": correct,
            "incorrect": len(boundary_predictions) - correct,
            "accuracy": float(accuracy_score(actual, predicted)),
            "actual_category_counts": dict(sorted(Counter(actual).items())),
            "predicted_category_counts": dict(sorted(Counter(predicted).items())),
        }

    metrics = {
        "baseline_version": "rules-v2",
        "dataset": GOLD_PATH.name,
        "record_count": total_records,
        "gold_review": {
            "status": manifest["review_status"],
            "reviewed_on": manifest["reviewed_on"],
        },
        "limitations": [
            "Labels originated from the reviewed taxonomy before manual approval.",
            "Fallen-tree boundary cases contain a documented synthetic obstruction clause.",
            "This gold set must not be used to tune rules-v2.",
        ],
        "labels": CATEGORIES,
        "overall": {
            "accuracy": float(accuracy_score(actual_categories, predicted_categories)),
            "macro_precision": float(macro_precision),
            "macro_recall": float(macro_recall),
            "macro_f1_score": float(macro_f1),
        },
        "per_category": per_category,
        "per_boundary": per_boundary,
        "confusion_matrix": {
            "rows": "actual",
            "columns": "predicted",
            "labels": CATEGORIES,
            "values": matrix.tolist(),
        },
    }

    write_json(PREDICTIONS_PATH, prediction_records)
    write_json(METRICS_PATH, metrics)

    print(f"Evaluated {total_records} approved gold records")
    print(f"Accuracy: {metrics['overall']['accuracy']:.4f}")
    print(f"Macro-F1: {metrics['overall']['macro_f1_score']:.4f}")
    print(f"Predictions: {PREDICTIONS_PATH}")
    print(f"Metrics: {METRICS_PATH}")


if __name__ == "__main__":
    main()
