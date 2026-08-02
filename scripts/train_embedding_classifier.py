from sentence_transformers import SentenceTransformer
import json
import joblib
from pathlib import Path
import numpy as np
import resource
import time
from civicproof.domain.incidents import IncidentCategory
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

model_name = 'qwen3-embedding-0.6b-v1'

hf_models = {
    'bge-small-v1': 'BAAI/bge-small-en-v1.5',
    'qwen3-embedding-0.6b-v1': 'Qwen/Qwen3-Embedding-0.6B'
}

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = PROJECT_ROOT / "nyc311_train.json"
VALIDATION_PATH = PROJECT_ROOT / "nyc311_validation.json"
TEST_PATH = PROJECT_ROOT / "nyc311_test.json"
GOLD_TEST_PATH = PROJECT_ROOT / "nyc311_gold_test.json"
MAPPING_PATH = PROJECT_ROOT / "complaint_mapping.json"
EVALUATION_DIR = PROJECT_ROOT / "artifacts" / "models" / model_name
ENCODER_PATH = EVALUATION_DIR / "encoder.joblib"
MODEL_PATH = EVALUATION_DIR / "model.joblib"
PREDICTIONS_PATH = EVALUATION_DIR / "validation_pred.json"
METRICS_PATH = EVALUATION_DIR / "validation_metrics.json"
CATEGORIES = [category.value for category in IncidentCategory]
EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

hf_model_name = hf_models[model_name]
train_file_path = 'nyc311_train.json'
validation_file_path = 'nyc311_validation.json'
model = SentenceTransformer(hf_model_name)

encoder = LabelEncoder()

def generate_embeddings(sentences):
    embeddings = model.encode(sentences, normalize_embeddings=True)
    return embeddings

def encode_categories(categories):
    encoded = encoder.fit_transform(categories)
    return encoded

def inverse_encode(encoded_categories):
    categories = encoder.inverse_transform(encoded_categories)
    return categories

def train_classifier(embeddings, categories):
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(embeddings, categories)
    return model

if __name__ == '__main__':
    with MAPPING_PATH.open(encoding="utf-8") as file:
        mapping = json.load(file)
    train_sentences = []
    train_categories = []
    with open(train_file_path, 'r') as f:
        train_data = json.load(f)
    for record in train_data:
        sentence = record['complaint_type'] + ' : ' + record['descriptor']
        train_sentences.append(sentence)
        train_categories.append(record['category'])
    embedded_train_sentences = generate_embeddings(train_sentences)
    encoded_train_categories = encode_categories(train_categories)
    encoded_categories = np.array(encoded_train_categories)
    classifier = train_classifier(embedded_train_sentences, encoded_train_categories)
    joblib.dump(encoder, ENCODER_PATH)
    joblib.dump(classifier, MODEL_PATH)
    with open(validation_file_path, 'r') as f:
        validation_data = json.load(f)
    validation_sentences = []
    validation_pred = []
    validation_actual = []
    for record in validation_data:
        sentence = record['complaint_type'] + ' : ' + record['descriptor']
        validation_sentences.append(sentence)
        validation_actual.append(record['category'])
    validation_inference_started = time.perf_counter()
    embedding_inference_started = time.perf_counter()
    embedded_validation_sentences = generate_embeddings(validation_sentences)
    embedding_inference_seconds = time.perf_counter() - embedding_inference_started
    classifier_inference_started = time.perf_counter()
    validation_pred = encoder.inverse_transform(classifier.predict(embedded_validation_sentences))
    classifier_inference_seconds = time.perf_counter() - classifier_inference_started
    validation_inference_seconds = time.perf_counter() - validation_inference_started
    prediction_records = []
    for index, record in enumerate(validation_data):
        prediction_records.append(
            {
                "unique_key": record["unique_key"],
                "complaint_type": record["complaint_type"],
                "descriptor": record["descriptor"],
                "input_text": validation_sentences[index],
                "category": {
                    "actual": validation_actual[index],
                    "predicted": validation_pred[index],
                    "correct": validation_actual[index] == validation_pred[index],
                },
            }
        )
    precision, recall, f1, support = precision_recall_fscore_support(
        validation_actual,
        validation_pred,
        labels=CATEGORIES,
        average=None,
        zero_division=0,
    )
    matrix = confusion_matrix(
        validation_actual,
        validation_pred,
        labels=CATEGORIES,
    )
    per_category = {}
    total_records = len(validation_actual)
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
        validation_actual,
        validation_pred,
        labels=CATEGORIES,
        average="macro",
        zero_division=0,
    )
    validation_metrics = {
        "model_name": model_name,
        "hf_model_name": hf_model_name,
        "classifier": "LogisticRegression",
        "model_profile": {
            "parameter_count": int(sum(parameter.numel() for parameter in model.parameters())),
            "weight_memory_mb": float(
                sum(parameter.numel() * parameter.element_size() for parameter in model.parameters())
                / (1024 * 1024)
            ),
            "embedding_dimension": int(embedded_validation_sentences.shape[1]),
            "embedding_dtype": str(embedded_validation_sentences.dtype),
            "stored_vector_bytes": int(
                embedded_validation_sentences.shape[1]
                * embedded_validation_sentences.dtype.itemsize
            ),
        },
        "performance": {
            "inference_seconds": float(validation_inference_seconds),
            "records_per_second": float(len(validation_actual) / validation_inference_seconds),
            "peak_process_memory_mb": float(
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
            ),
            "components": {
                "embedding_seconds": float(embedding_inference_seconds),
                "classifier_seconds": float(classifier_inference_seconds),
            },
        },
        "dataset": VALIDATION_PATH.name,
        "record_count": len(validation_actual),
        "ground_truth": {
            "type": "mapping-derived weak labels",
            "mapping": MAPPING_PATH.name,
            "mapping_version": mapping["version"],
            "limitation": "Agreement measures taxonomy regression, not independent generalization.",
        },
        "labels": CATEGORIES,
        "overall": {
            "accuracy": float(accuracy_score(validation_actual, validation_pred)),
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
    with open(PREDICTIONS_PATH, 'w') as f:
        json.dump(prediction_records, f, indent=2)
        f.write('\n')
    with open(METRICS_PATH, 'w') as f:
        json.dump(validation_metrics, f, indent=2)
        f.write('\n')
    print('Validation Accuracy:', validation_metrics['overall']['accuracy'])
    print('Macro Precision:', validation_metrics['overall']['macro_precision'])
    print('Macro Recall:', validation_metrics['overall']['macro_recall'])
    print('Macro-F1:', validation_metrics['overall']['macro_f1_score'])
