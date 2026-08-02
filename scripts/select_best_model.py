import json
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = PROJECT_ROOT / "artifacts" / "models"
OUTPUT_PATH = MODELS_DIR / "model_comparison.json"
QUALITY_TIE_TOLERANCE = 0.005

def load_metrics(path):
    with path.open(encoding="utf-8") as file:
        metrics = json.load(file)
    required_sections = ["model_name", "dataset", "record_count", "labels", "overall"]
    missing_sections = [section for section in required_sections if section not in metrics]
    if missing_sections:
        raise ValueError(f"{path} is missing required sections: {missing_sections}")
    return metrics

def validate_comparability(metrics_by_path):
    reference_path, reference = metrics_by_path[0]
    reference_contract = {
        "dataset": reference["dataset"],
        "record_count": reference["record_count"],
        "labels": reference["labels"],
        "mapping_version": reference["ground_truth"]["mapping_version"],
    }
    for path, metrics in metrics_by_path[1:]:
        candidate_contract = {
            "dataset": metrics["dataset"],
            "record_count": metrics["record_count"],
            "labels": metrics["labels"],
            "mapping_version": metrics["ground_truth"]["mapping_version"],
        }
        if candidate_contract != reference_contract:
            raise ValueError(
                f"Metrics in {path} are not comparable with {reference_path}: "
                f"{candidate_contract} != {reference_contract}"
            )
    return reference_contract

def build_candidate(path, metrics):
    return {
        "model_name": metrics["model_name"],
        "hf_model_name": metrics.get("hf_model_name"),
        "classifier": metrics.get("classifier"),
        "metrics_file": str(path.relative_to(PROJECT_ROOT)),
        "scores": metrics["overall"],
        "performance": metrics["performance"],
        "model_profile": metrics["model_profile"],
    }

def efficiency_key(candidate):
    performance = candidate["performance"]
    profile = candidate["model_profile"]
    return (
        performance["records_per_second"],
        -performance["peak_process_memory_mb"],
        -profile["weight_memory_mb"],
        -profile["stored_vector_bytes"],
    )

def add_best_deltas(candidate, best):
    candidate_performance = candidate["performance"]
    best_performance = best["performance"]
    candidate_profile = candidate["model_profile"]
    best_profile = best["model_profile"]
    candidate["deltas_from_best"] = {
        "accuracy": candidate["scores"]["accuracy"] - best["scores"]["accuracy"],
        "macro_f1_score": (
            candidate["scores"]["macro_f1_score"]
            - best["scores"]["macro_f1_score"]
        ),
        "throughput_ratio": (
            candidate_performance["records_per_second"]
            / best_performance["records_per_second"]
        ),
        "peak_memory_ratio": (
            candidate_performance["peak_process_memory_mb"]
            / best_performance["peak_process_memory_mb"]
        ),
        "weight_memory_ratio": (
            candidate_profile["weight_memory_mb"]
            / best_profile["weight_memory_mb"]
        ),
        "stored_vector_size_ratio": (
            candidate_profile["stored_vector_bytes"]
            / best_profile["stored_vector_bytes"]
        ),
    }
    return candidate

if __name__ == "__main__":
    metric_paths = sorted(MODELS_DIR.glob("*/validation_metrics.json"))
    if not metric_paths:
        raise FileNotFoundError(f"No validation metrics found under {MODELS_DIR}")
    metrics_by_path = [(path, load_metrics(path)) for path in metric_paths]
    evaluation_contract = validate_comparability(metrics_by_path)
    candidates = [build_candidate(path, metrics) for path, metrics in metrics_by_path]
    rules_benchmarks = [candidate for candidate in candidates if candidate["classifier"] == "DeterministicRules"]
    learned_candidates = [candidate for candidate in candidates if candidate["classifier"] != "DeterministicRules"]
    if not learned_candidates:
        raise ValueError("No learned-model candidates were found")
    highest_macro_f1 = max(candidate["scores"]["macro_f1_score"] for candidate in learned_candidates)
    quality_tied_candidates = [
        candidate
        for candidate in learned_candidates
        if highest_macro_f1 - candidate["scores"]["macro_f1_score"]
        <= QUALITY_TIE_TOLERANCE
    ]
    best = max(quality_tied_candidates, key=efficiency_key)
    competitors = [candidate for candidate in learned_candidates if candidate is not best]
    competitors.sort(key=lambda candidate: candidate["scores"]["macro_f1_score"], reverse=True)
    competitors = [add_best_deltas(candidate, best) for candidate in competitors]
    comparison = {
        "generated_at": datetime.now(UTC).isoformat(),
        "evaluation_contract": evaluation_contract,
        "selection_policy": {
            "eligible_models": "Learned models only; deterministic rules remain a benchmark",
            "primary_metric": "macro_f1_score",
            "quality_tie_tolerance": QUALITY_TIE_TOLERANCE,
            "tie_breakers": [
                "higher records_per_second",
                "lower peak_process_memory_mb",
                "lower weight_memory_mb",
                "lower stored_vector_bytes",
            ],
        },
        "best": best,
        "selection_reason": (
            f"{best['model_name']} was within "
            f"{QUALITY_TIE_TOLERANCE:.3f} macro-F1 of the best quality score and won "
            "the declared efficiency tie-breakers."
        ),
        "competitors": competitors,
        "rules_benchmarks": rules_benchmarks,
    }
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(comparison, file, indent=2)
        file.write("\n")
    print(f"best: {best['model_name']}")
    print(f"Macro-F1: {best['scores']['macro_f1_score']:.4f}")
    print(f"Comparison: {OUTPUT_PATH}")
