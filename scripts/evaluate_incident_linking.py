import argparse
import json
from pathlib import Path
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from civicproof.services.incident_linking import LINKING_RULES, LINK_SCORE_THRESHOLD

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / 'data' / 'incident_linking_gold.json'
DEFAULT_METRICS_PATH = PROJECT_ROOT / 'artifacts' / 'evaluation' / 'incident_linking_metrics.json'

def calculate_metrics(labels, predictions):
    precision, recall, f1, support = precision_recall_fscore_support(
        labels,
        predictions,
        average='binary',
        zero_division=0
    )
    return {
        'accuracy': accuracy_score(labels, predictions),
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'confusion_matrix': confusion_matrix(labels, predictions, labels=[False, True]).tolist(),
        'record_count': len(labels)
    }

def predict_pair(record, model_name):
    category = record['category']
    rule = LINKING_RULES[category]
    spatial_score = max(0.0, 1.0 - record['distance_meters'] / rule['radius_meters'])
    temporal_score = max(
        0.0,
        1.0 - record['time_difference_seconds'] / (rule['hours'] * 60 * 60)
    )
    category_match = record.get('category_match', True)
    semantic_similarity = record.get('semantic_similarity')
    if model_name == 'distance_only':
        score = spatial_score
    elif model_name == 'distance_time':
        score = spatial_score * 0.6 + temporal_score * 0.4
    elif model_name == 'distance_time_category':
        score = (spatial_score * 0.6 + temporal_score * 0.4) if category_match else 0.0
    else:
        if semantic_similarity is None:
            score = spatial_score * 0.6 + temporal_score * 0.4
        else:
            semantic_score = max(0.0, min(1.0, semantic_similarity))
            score = spatial_score * 0.4 + temporal_score * 0.25 + semantic_score * 0.35
        if not category_match:
            score = 0.0
    return score >= LINK_SCORE_THRESHOLD

def evaluate_linking(data_path, metrics_path):
    with open(data_path, 'r') as f:
        records = json.load(f)
    labels = [record['same_event'] for record in records]
    model_names = [
        'distance_only',
        'distance_time',
        'distance_time_category',
        'hybrid_semantic'
    ]
    metrics = {
        'threshold': LINK_SCORE_THRESHOLD,
        'models': {}
    }
    for model_name in model_names:
        predictions = [
            predict_pair(record, model_name)
            for record in records
        ]
        metrics['models'][model_name] = calculate_metrics(labels, predictions)
    best_model = max(
        metrics['models'],
        key=lambda model_name: metrics['models'][model_name]['f1']
    )
    metrics['best_model'] = best_model
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    print(json.dumps(metrics, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Evaluate incident linking rules')
    parser.add_argument('--data-path', type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument('--metrics-path', type=Path, default=DEFAULT_METRICS_PATH)
    args = parser.parse_args()
    evaluate_linking(args.data_path, args.metrics_path)
