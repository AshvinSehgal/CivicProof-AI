import argparse
import json
from pathlib import Path
from civicproof.domain.incidents import IncidentCategory
import joblib
from sentence_transformers import SentenceTransformer
import numpy as np

model_name = 'bge-small-v1-final'

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAPPING_PATH = PROJECT_ROOT / "complaint_mapping.json"
MODELS_PATH = PROJECT_ROOT / "artifacts" / "models"
MODEL_FOLDER_PATH = MODELS_PATH / model_name
MODEL_CONFIG_PATH = MODEL_FOLDER_PATH / "model_config.json"
ENCODER_PATH = MODEL_FOLDER_PATH / "encoder.joblib"
MODEL_PATH = MODEL_FOLDER_PATH / "model.joblib"
CATEGORIES = np.array([category.value for category in IncidentCategory])

class EmbeddingClassifier():
    def __init__(self):
        self.embedding_model = None
        self.classifier = None
        self.encoder = None
        self.normalize_embeddings = None
        self.threshold = 0.0
        self.encoded_categories = None
        self.model_name = None

    def load_model(self):
        if not MODEL_CONFIG_PATH.is_file():
            raise FileNotFoundError(f"Could not find model_config.json at {MODEL_CONFIG_PATH.resolve()}")
        if not MODEL_PATH.is_file():
            raise FileNotFoundError(f"Could not find model.joblib at {MODEL_PATH.resolve()}")
        if not ENCODER_PATH.is_file():
            raise FileNotFoundError(f"Could not find encoder.joblib at {ENCODER_PATH.resolve()}")
        with open(MODEL_CONFIG_PATH, "r") as f:
            model_config = json.load(f)
        if model_config['test_status'] != 'evaluated_and_frozen':
            raise ValueError("The model has not been evaluated and frozen")
        if isinstance(model_config['threshold'], bool) or not isinstance(model_config['threshold'], (int, float)) or model_config['threshold'] < 0 or model_config['threshold'] > 1:
            raise ValueError("The model threshold must be a number between 0 and 1")
        if not isinstance(model_config['normalize_embeddings'], bool):
            raise ValueError("normalize_embeddings must be a boolean")
        if set(model_config['labels']) != set(CATEGORIES.tolist()):
            raise ValueError("The configured labels do not match the incident categories")
        if model_config['model_name'] != MODEL_FOLDER_PATH.name:
            raise ValueError("The configured model name does not match the model folder")
        classifier = joblib.load(MODEL_PATH)
        encoder = joblib.load(ENCODER_PATH)
        embedding_model = SentenceTransformer(model_config['hf_model_name'])
        if encoder.classes_.tolist() != model_config['labels']:
            raise ValueError("The encoder labels do not match the configured labels")
        classifier_categories = encoder.inverse_transform(classifier.classes_).tolist()
        if classifier_categories != model_config['labels']:
            raise ValueError("The classifier labels do not match the configured labels")
        if classifier.n_features_in_ != embedding_model.get_embedding_dimension():
            raise ValueError("The classifier input dimension does not match the embedding dimension")
        encoded_categories = encoder.transform(CATEGORIES)
        encoded_categories = CATEGORIES[encoded_categories]
        self.threshold = model_config['threshold']
        self.normalize_embeddings = model_config['normalize_embeddings']
        self.embedding_model = embedding_model
        self.classifier = classifier
        self.encoder = encoder
        self.encoded_categories = encoded_categories
        self.model_name = model_config['model_name']

    def predict(self, complaint_type, descriptor):
        if self.embedding_model is None or self.classifier is None or self.encoder is None:
            raise RuntimeError("The embedding classifier has not been loaded")
        if complaint_type is None or complaint_type == "" or complaint_type.isspace():
            raise ValueError("complaint_type must be a valid string")
        if descriptor is None or descriptor == "" or descriptor.isspace():
            raise ValueError("descriptor must be a valid string")
        sentence = [complaint_type + ' : ' + descriptor]
        embedding = self.embedding_model.encode(sentence, normalize_embeddings=self.normalize_embeddings)
        pred_probs = self.classifier.predict_proba(embedding)[0]
        max_prob = np.max(pred_probs)
        pred_category = self.encoded_categories[np.argmax(pred_probs)]
        probs = {
            self.encoded_categories[i].item(): pred_probs[i].item()
            for i in range(len(self.encoded_categories))
        }
        requires_human_review = bool(max_prob < self.threshold)
        return {
            'category': pred_category.item(),
            'confidence': max_prob.item(),
            'probabilities': probs,
            'requires_human_review': requires_human_review,
            'model_name': self.model_name,
            'threshold': self.threshold
        }

    def encode_incident(self, complaint_type, descriptor, description):
        embeddings = self.encode_incidents([
            (complaint_type, descriptor, description)
        ])
        return embeddings[0]

    def encode_incidents(self, incidents):
        if self.embedding_model is None:
            raise RuntimeError("The embedding classifier has not been loaded")
        sentences = [
            complaint_type + ' : ' + descriptor + ' : ' + description
            for complaint_type, descriptor, description in incidents
        ]
        embeddings = self.embedding_model.encode(
            sentences,
            normalize_embeddings=self.normalize_embeddings
        )
        return embeddings.tolist()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run classifier on given complaint_type and descriptor')
    parser.add_argument('--complaint_type', type=str, required=True, help='Type of complaint')
    parser.add_argument('--descriptor', type=str, required=True, help='Short description of complaint')
    args = parser.parse_args()
    model = EmbeddingClassifier()
    model.load_model()
    pred = model.predict(args.complaint_type, args.descriptor)
    print(pred)
