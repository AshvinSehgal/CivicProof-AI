import argparse
import json
from pathlib import Path
from civicproof.domain.incidents import IncidentCategory
import joblib
from sentence_transformers import SentenceTransformer
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TRAIN_PATH = PROJECT_ROOT / "nyc311_train.json"
VALIDATION_PATH = PROJECT_ROOT / "nyc311_validation.json"
TEST_PATH = PROJECT_ROOT / "nyc311_test.json"
GOLD_TEST_PATH = PROJECT_ROOT / "nyc311_gold_test.json"
MAPPING_PATH = PROJECT_ROOT / "complaint_mapping.json"
MODELS_PATH = PROJECT_ROOT / "artifacts" / "models"

with open(MODELS_PATH / "model_comparison.json", "r") as f:
    data = json.load(f)
model_name = data['best']['model_name']
hf_model_name = data['best']['hf_model_name']

MODEL_FOLDER_PATH = MODELS_PATH / model_name
ENCODER_PATH = MODEL_FOLDER_PATH / "encoder.joblib"
MODEL_PATH = MODEL_FOLDER_PATH / "model.joblib"
CATEGORIES = np.array([category.value for category in IncidentCategory])

model = SentenceTransformer(hf_model_name)
classifier = joblib.load(MODEL_PATH)
encoder = joblib.load(ENCODER_PATH)
threshold = 0.4

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='User will provide the complaint type and descriptor')
    parser.add_argument('--complaint_type', type=str, required=True, help='Type of complaint')
    parser.add_argument('--descriptor', type=str, required=True, help='Description of complaint')
    args = parser.parse_args()
    embeddings = model.encode([args.complaint_type + " : " + args.descriptor], normalize_embeddings=True)
    encoded_categories = encoder.transform(CATEGORIES)
    CATEGORIES = CATEGORIES[encoded_categories]
    probs = classifier.predict_proba(embeddings)[0]
    print('Predicted probabilities:')
    for i, category in enumerate(CATEGORIES):
        print(category,':',probs[i])
    max_prob = np.max(probs)
    if max_prob >= threshold:
        print('Predicted Category:', CATEGORIES[np.argmax(probs)])
    else:
        print('Predicted Category:', 'requires_human_review')