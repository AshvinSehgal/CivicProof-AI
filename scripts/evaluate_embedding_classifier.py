from sentence_transformers import SentenceTransformer
import json
import joblib
from pathlib import Path
import numpy as np
import resource
import time
from civicproof.domain.incidents import IncidentCategory
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_PATH = PROJECT_ROOT / "nyc311_test.json"
MAPPING_PATH = PROJECT_ROOT / "complaint_mapping.json"
MODELS_PATH = PROJECT_ROOT / "artifacts" / "models"
COMPARISON_PATH = MODELS_PATH / "model_comparison.json"

with open(COMPARISON_PATH, 'r') as f:
    comparison = json.load(f)

selected_model_name = comparison['best']['model_name']
model_name = selected_model_name + '-final'
MODEL_FOLDER_PATH = MODELS_PATH / model_name
ENCODER_PATH = MODEL_FOLDER_PATH / "encoder.joblib"
MODEL_PATH = MODEL_FOLDER_PATH / "model.joblib"
CONFIG_PATH = MODEL_FOLDER_PATH / "model_config.json"
PREDICTIONS_PATH = MODEL_FOLDER_PATH / "test_pred.json"
METRICS_PATH = MODEL_FOLDER_PATH / "test_metrics.json"
CATEGORIES = [category.value for category in IncidentCategory]

with open(CONFIG_PATH, 'r') as f:
    model_config = json.load(f)

hf_model_name = model_config['hf_model_name']
threshold = model_config['threshold']
model = SentenceTransformer(hf_model_name)
classifier = joblib.load(MODEL_PATH)
encoder = joblib.load(ENCODER_PATH)

def generate_embeddings(sentences):
    embeddings = model.encode(sentences, normalize_embeddings=True)
    return embeddings

if __name__ == '__main__':
    if METRICS_PATH.exists():
        raise FileExistsError('The final test has already been evaluated and frozen')
    with open(TEST_PATH, 'r') as f:
        test_data = json.load(f)
    with open(MAPPING_PATH, 'r') as f:
        mapping = json.load(f)
    test_sentences = []
    test_actual = []
    for record in test_data:
        sentence = record['complaint_type'] + ' : ' + record['descriptor']
        test_sentences.append(sentence)
        test_actual.append(record['category'])
    test_inference_started = time.perf_counter()
    embedding_inference_started = time.perf_counter()
    embedded_test_sentences = generate_embeddings(test_sentences)
    embedding_inference_seconds = time.perf_counter() - embedding_inference_started
    classifier_inference_started = time.perf_counter()
    encoded_test_pred = classifier.predict(embedded_test_sentences)
    test_pred = encoder.inverse_transform(encoded_test_pred)
    test_probs = classifier.predict_proba(embedded_test_sentences)
    classifier_inference_seconds = time.perf_counter() - classifier_inference_started
    test_inference_seconds = time.perf_counter() - test_inference_started
    probability_categories = encoder.inverse_transform(classifier.classes_)
    prediction_records = []
    accepted_count = 0
    accepted_correct = 0
    for index, record in enumerate(test_data):
        confidence = float(np.max(test_probs[index]))
        requires_human_review = confidence < threshold
        if requires_human_review == False:
            accepted_count += 1
            if test_actual[index] == test_pred[index]:
                accepted_correct += 1
        probabilities = {}
        for probability_index, category in enumerate(probability_categories):
            probabilities[category] = float(test_probs[index][probability_index])
        prediction_records.append(
            {
                "unique_key": record["unique_key"],
                "complaint_type": record["complaint_type"],
                "descriptor": record["descriptor"],
                "input_text": test_sentences[index],
                "category": {
                    "actual": test_actual[index],
                    "predicted": test_pred[index],
                    "correct": test_actual[index] == test_pred[index],
                },
                "confidence": confidence,
                "probabilities": probabilities,
                "requires_human_review": requires_human_review,
            }
        )
    precision, recall, f1, support = precision_recall_fscore_support(
        test_actual,
        test_pred,
        labels=CATEGORIES,
        average=None,
        zero_division=0,
    )
    matrix = confusion_matrix(
        test_actual,
        test_pred,
        labels=CATEGORIES,
    )
    per_category = {}
    total_records = len(test_actual)
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
        test_actual,
        test_pred,
        labels=CATEGORIES,
        average="macro",
        zero_division=0,
    )
    human_review_count = total_records - accepted_count
    if accepted_count == 0:
        selective_accuracy = None
    else:
        selective_accuracy = accepted_correct / accepted_count
    test_metrics = {
        "evaluation_status": "final_frozen",
        "model_name": model_name,
        "hf_model_name": hf_model_name,
        "classifier": "LogisticRegression",
        "model_profile": {
            "parameter_count": int(sum(parameter.numel() for parameter in model.parameters())),
            "weight_memory_mb": float(
                sum(parameter.numel() * parameter.element_size() for parameter in model.parameters())
                / (1024 * 1024)
            ),
            "embedding_dimension": int(embedded_test_sentences.shape[1]),
            "embedding_dtype": str(embedded_test_sentences.dtype),
            "stored_vector_bytes": int(
                embedded_test_sentences.shape[1]
                * embedded_test_sentences.dtype.itemsize
            ),
        },
        "performance": {
            "inference_seconds": float(test_inference_seconds),
            "records_per_second": float(total_records / test_inference_seconds),
            "milliseconds_per_record": float(test_inference_seconds * 1000 / total_records),
            "peak_process_memory_mb": float(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
            ),
            "components": {
                "embedding_seconds": float(embedding_inference_seconds),
                "classifier_seconds": float(classifier_inference_seconds),
            },
        },
        "dataset": TEST_PATH.name,
        "record_count": total_records,
        "ground_truth": {
            "type": "mapping-derived weak labels",
            "mapping": MAPPING_PATH.name,
            "mapping_version": mapping["version"],
            "limitation": "Agreement measures taxonomy regression, not independent generalization.",
        },
        "labels": CATEGORIES,
        "overall": {
            "accuracy": float(accuracy_score(test_actual, test_pred)),
            "macro_precision": float(macro_precision),
            "macro_recall": float(macro_recall),
            "macro_f1_score": float(macro_f1),
        },
        "confidence": {
            "threshold": threshold,
            "accepted_count": accepted_count,
            "human_review_count": human_review_count,
            "coverage": float(accepted_count / total_records),
            "human_review_rate": float(human_review_count / total_records),
            "selective_accuracy": selective_accuracy,
        },
        "per_category": per_category,
        "confusion_matrix": {
            "rows": "actual",
            "columns": "predicted",
            "labels": CATEGORIES,
            "values": matrix.tolist(),
        },
    }
    with open(PREDICTIONS_PATH, 'w') as f:
        json.dump(prediction_records, f, indent=2)
        f.write('\n')
    with open(METRICS_PATH, 'w') as f:
        json.dump(test_metrics, f, indent=2)
        f.write('\n')
    model_config['test_status'] = 'evaluated_and_frozen'
    model_config['test_metrics_file'] = str(METRICS_PATH.relative_to(PROJECT_ROOT))
    with open(CONFIG_PATH, 'w') as f:
        json.dump(model_config, f, indent=2)
        f.write('\n')
    print('Test Accuracy:', test_metrics['overall']['accuracy'])
    print('Macro Precision:', test_metrics['overall']['macro_precision'])
    print('Macro Recall:', test_metrics['overall']['macro_recall'])
    print('Macro-F1:', test_metrics['overall']['macro_f1_score'])
    print('Coverage:', test_metrics['confidence']['coverage'])
    print('Selective Accuracy:', test_metrics['confidence']['selective_accuracy'])
    print('Human Review Rate:', test_metrics['confidence']['human_review_rate'])
