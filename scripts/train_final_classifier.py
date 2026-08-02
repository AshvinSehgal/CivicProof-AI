from sentence_transformers import SentenceTransformer
import json
import joblib
from pathlib import Path
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAIN_PATH = PROJECT_ROOT / "nyc311_train.json"
VALIDATION_PATH = PROJECT_ROOT / "nyc311_validation.json"
MAPPING_PATH = PROJECT_ROOT / "complaint_mapping.json"
MODELS_PATH = PROJECT_ROOT / "artifacts" / "models"
COMPARISON_PATH = MODELS_PATH / "model_comparison.json"

with open(COMPARISON_PATH, 'r') as f:
    comparison = json.load(f)

selected_model_name = comparison['best']['model_name']
model_name = selected_model_name + '-final'
hf_model_name = comparison['best']['hf_model_name']

EVALUATION_DIR = MODELS_PATH / model_name
ENCODER_PATH = EVALUATION_DIR / "encoder.joblib"
MODEL_PATH = EVALUATION_DIR / "model.joblib"
CONFIG_PATH = EVALUATION_DIR / "model_config.json"
EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

model = SentenceTransformer(hf_model_name)
encoder = LabelEncoder()
threshold = 0.4

def generate_embeddings(sentences):
    embeddings = model.encode(sentences, normalize_embeddings=True)
    return embeddings

def encode_categories(categories):
    encoded = encoder.fit_transform(categories)
    return encoded

def train_classifier(embeddings, categories):
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(embeddings, categories)
    return model

if __name__ == '__main__':
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, 'r') as f:
            existing_config = json.load(f)
        if existing_config['test_status'] == 'evaluated_and_frozen':
            raise FileExistsError('The final model and test evaluation have already been frozen')
    with open(TRAIN_PATH, 'r') as f:
        train_data = json.load(f)
    with open(VALIDATION_PATH, 'r') as f:
        validation_data = json.load(f)
    with open(MAPPING_PATH, 'r') as f:
        mapping = json.load(f)
    final_train_data = train_data + validation_data
    train_sentences = []
    train_categories = []
    for record in final_train_data:
        sentence = record['complaint_type'] + ' : ' + record['descriptor']
        train_sentences.append(sentence)
        train_categories.append(record['category'])
    embedded_train_sentences = generate_embeddings(train_sentences)
    encoded_train_categories = encode_categories(train_categories)
    classifier = train_classifier(embedded_train_sentences, encoded_train_categories)
    joblib.dump(encoder, ENCODER_PATH)
    joblib.dump(classifier, MODEL_PATH)
    model_config = {
        "model_name": model_name,
        "selected_model_name": selected_model_name,
        "hf_model_name": hf_model_name,
        "classifier": "LogisticRegression",
        "normalize_embeddings": True,
        "threshold": threshold,
        "training_datasets": [TRAIN_PATH.name, VALIDATION_PATH.name],
        "training_record_count": len(final_train_data),
        "mapping": MAPPING_PATH.name,
        "mapping_version": mapping['version'],
        "labels": encoder.classes_.tolist(),
        "test_status": "not_evaluated",
    }
    with open(CONFIG_PATH, 'w') as f:
        json.dump(model_config, f, indent=2)
        f.write('\n')
    print('Final model:', model_name)
    print('Training records:', len(final_train_data))
    print('Model:', MODEL_PATH)
    print('Encoder:', ENCODER_PATH)
    print('Config:', CONFIG_PATH)
