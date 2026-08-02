import json
from pathlib import Path
import resource
import time
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from civicproof.domain.incidents import IncidentCategory, IncidentReport, ReportSource
from civicproof.services.triage import BaselineTriageService

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_PATH = PROJECT_ROOT / "nyc311_validation.json"
MAPPING_PATH = PROJECT_ROOT / "complaint_mapping.json"
EVALUATION_DIR = PROJECT_ROOT / "artifacts" / "models" / "baseline"
PREDICTIONS_PATH = EVALUATION_DIR / "validation_pred.json"
METRICS_PATH = EVALUATION_DIR / "validation_metrics.json"
CATEGORIES = [category.value for category in IncidentCategory]
EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
with VALIDATION_PATH.open(encoding="utf-8") as file:
    data = json.load(file)
with MAPPING_PATH.open(encoding="utf-8") as file:
    mapping = json.load(file)
triage_service = BaselineTriageService()
prediction_records = []
actual_categories = []
predicted_categories = []
validation_inference_started = time.perf_counter()
for record in data:
    report = IncidentReport(
        source=ReportSource.OPEN311,
        external_id=record["unique_key"],
        description=f"{record['complaint_type']}: {record['descriptor']}",
        latitude=float(record["latitude"]),
        longitude=float(record["longitude"]),
        media_urls=[],
    )
    predicted = triage_service.triage(report).category.value
    actual = IncidentCategory(record["category"]).value
    actual_categories.append(actual)
    predicted_categories.append(predicted)
    prediction_records.append(
        {
            "unique_key": record["unique_key"],
            "created_date": record["created_date"],
            "agency": record["agency"],
            "complaint_type": record["complaint_type"],
            "descriptor": record["descriptor"],
            "status": record["status"],
            "borough": record["borough"],
            "incident_zip": record["incident_zip"],
            "latitude": record["latitude"],
            "longitude": record["longitude"],
            "category": {
                "actual": actual,
                "predicted": predicted,
                "correct": actual == predicted,
            },
        }
    )
validation_inference_seconds = time.perf_counter() - validation_inference_started
precision, recall, f1, support = precision_recall_fscore_support(
    actual_categories,
    predicted_categories,
    labels=CATEGORIES,
    average=None,
    zero_division=0,
)
matrix = confusion_matrix(
    actual_categories,
    predicted_categories,
    labels=CATEGORIES,
)
per_category = {}
total_records = len(actual_categories)
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
metrics = {
    "model_name": "baseline",
    "hf_model_name": None,
    "classifier": "DeterministicRules",
    "baseline_version": "rules-v2",
    "model_profile": {
        "parameter_count": 0,
        "weight_memory_mb": 0.0,
        "embedding_dimension": None,
        "embedding_dtype": None,
        "stored_vector_bytes": None,
    },
    "performance": {
        "inference_seconds": float(validation_inference_seconds),
        "records_per_second": float(total_records / validation_inference_seconds),
        "peak_process_memory_mb": float(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
        ),
        "components": {
            "rules_seconds": float(validation_inference_seconds),
        },
    },
    "dataset": VALIDATION_PATH.name,
    "record_count": total_records,
    "ground_truth": {
        "type": "mapping-derived weak labels",
        "mapping": MAPPING_PATH.name,
        "mapping_version": mapping["version"],
        "limitation": "Agreement measures taxonomy regression, not independent generalization.",
    },
    "labels": CATEGORIES,
    "overall": {
        "accuracy": float(accuracy_score(actual_categories, predicted_categories)),
        "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall),
        "macro_f1_score": float(macro_f1),
    },
    "per_category": per_category,
    "confusion_matrix": {
        "rows": "actual",
        "columns": "predicted",
        "labels": CATEGORIES,
        "values": matrix.tolist(),
    },
}
with PREDICTIONS_PATH.open("w", encoding="utf-8") as file:
    json.dump(prediction_records, file, indent=2)
    file.write("\n")
with METRICS_PATH.open("w", encoding="utf-8") as file:
    json.dump(metrics, file, indent=2)
    file.write("\n")
print(f"Evaluated {total_records} validation records")
print(f"Accuracy: {metrics['overall']['accuracy']:.4f}")
print(f"Macro-F1: {metrics['overall']['macro_f1_score']:.4f}")
print(f"Predictions: {PREDICTIONS_PATH}")
print(f"Metrics: {METRICS_PATH}")
