import argparse
import json
from pathlib import Path
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from civicproof.services.incident_linking import LINKING_RULES, LINK_SCORE_THRESHOLD

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / 'data' / 'incident_linking_calibration.json'
DEFAULT_METRICS_PATH = PROJECT_ROOT / 'artifacts' / 'evaluation' / 'incident_linking_metrics.json'
DEFAULT_ERRORS_PATH = PROJECT_ROOT / 'artifacts' / 'evaluation' / 'incident_linking_errors.json'

def calculate_metrics(labels, predictions):
    precision, recall, f1, support = precision_recall_fscore_support(labels, predictions, average='binary', zero_division=0)
    true_negative, false_positive, false_negative, true_positive = (confusion_matrix(labels, predictions, labels=[False, True]).ravel())
    predicted_positive_count = true_positive + false_positive
    false_merge_rate = (false_positive / predicted_positive_count if predicted_positive_count > 0 else 0)
    return {
        'accuracy': float(accuracy_score(labels, predictions)),
        'precision': float(precision),
        'recall': float(recall),
        'f1': float(f1),
        'confusion_matrix': confusion_matrix(labels, predictions, labels=[False, True]).tolist(),
        'true_positive': int(true_positive),
        'false_positive': int(false_positive),
        'true_negative': int(true_negative),
        'false_negative': int(false_negative),
        'predicted_positive_count': int(predicted_positive_count),
        'false_merge_rate': float(false_merge_rate),
        'record_count': len(labels)
    }

def predict_pair(record, model_name, linking_config=None):
    category = record['category']
    if linking_config is not None:
        category_radii = linking_config['category_radii'][category]
        category_time_window = linking_config['category_time_windows'][category]
        threshold = linking_config['threshold']
    else:
        rule = LINKING_RULES[category]
        category_radii = LINKING_RULES[category]['radius_meters']
        category_time_window = LINKING_RULES[category]['hours'] * 60 * 60
        threshold = LINK_SCORE_THRESHOLD
    within_radius = (record['distance_meters'] <= category_radii)
    within_time_window = (record['time_difference_seconds'] <= category_time_window)
    spatial_score = max(0.0, 1.0 - record['distance_meters'] / category_radii)
    temporal_score = max(0.0, 1.0 - record['time_difference_seconds'] / category_time_window)
    category_match = record.get('category_match', True)
    semantic_similarity = record.get('semantic_similarity')
    if model_name == 'distance_only':
        score = spatial_score
    elif model_name == 'distance_time':
        score = spatial_score * 0.6 + temporal_score * 0.4
    elif model_name == 'distance_time_category':
        score = (spatial_score * 0.6 + temporal_score * 0.4) if category_match else 0.0
    else:
        if linking_config is not None:
            spatial_weight = linking_config['spatial_weight']
            semantic_weight = linking_config['semantic_weight']
            temporal_weight = linking_config['temporal_weight']
        else:
            spatial_weight = 0.4
            semantic_weight = 0.35
            temporal_weight = 0.25
        if semantic_similarity is None:
            non_semantic_weight = spatial_weight + temporal_weight
            spatial_weight = spatial_weight / non_semantic_weight
            temporal_weight = temporal_weight / non_semantic_weight
            score = spatial_score * spatial_weight + temporal_score * temporal_weight
        else:
            semantic_score = max(0.0, min(1.0, semantic_similarity))
            score = spatial_score * spatial_weight + temporal_score * temporal_weight + semantic_score * semantic_weight
        if not (within_radius and within_time_window and category_match):
            score = 0.0
    return {
        'score': score,
        'prediction': score >= threshold,
        'within_radius': within_radius,
        'within_time_window': within_time_window,
        'category_match': category_match
    }

def evaluate_linking(data_path, metrics_path, errors_path):
    with open(data_path, 'r') as f:
        records = json.load(f)
    labels = [record['same_event'] for record in records]
    model_names = ['distance_only', 'distance_time', 'distance_time_category', 'hybrid_semantic']
    metrics = {
        'threshold': LINK_SCORE_THRESHOLD,
        'models': {}
    }
    model_errors = []
    categories = sorted({record['category'] for record in records})
    for model_name in model_names:
        prediction_results = [predict_pair(record, model_name) for record in records]
        predictions = [prediction_result['prediction'] for prediction_result in prediction_results]
        metrics['models'][model_name] = {
            'overall': calculate_metrics(labels, predictions),
            'by_category': {}
        }
        for category in categories:
            category_labels = [labels[index] for index in range(len(records)) if records[index]['category'] == category]
            category_predictions = [predictions[index] for index in range(len(records)) if records[index]['category'] == category]
            metrics['models'][model_name]['by_category'][category] = calculate_metrics(category_labels, category_predictions)
        for index in range(len(records)):
            if predictions[index] != labels[index]:
                record = records[index]
                prediction_result = prediction_results[index]
                model_errors.append({
                    'model_name': model_name,
                    'incident_a': record['incident_a'],
                    'incident_b': record['incident_b'],
                    'category': record['category'],
                    'expected': labels[index],
                    'predicted': predictions[index],
                    'error_type': 'false_positive' if predictions[index] else 'false_negative',
                    'score': prediction_result['score'],
                    'distance_meters': record['distance_meters'],
                    'time_difference_seconds': record['time_difference_seconds'],
                    'semantic_similarity': record.get('semantic_similarity'),
                    'within_radius': prediction_result['within_radius'],
                    'within_time_window': prediction_result['within_time_window'],
                    'category_match': prediction_result['category_match'],
                    'review_rationale': record.get('review_rationale')
                })
    best_model = max(metrics['models'], key=lambda model_name: metrics['models'][model_name]['overall']['f1'])
    metrics['best_model'] = best_model
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    errors_path.parent.mkdir(parents=True, exist_ok=True)
    with open(errors_path, 'w') as f:
        json.dump({
            'data_file': data_path.name,
            'threshold': LINK_SCORE_THRESHOLD,
            'error_count': len(model_errors),
            'errors': model_errors
        }, f, indent=2)
    print(json.dumps(metrics, indent=2))
    print('Model errors:', errors_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Evaluate incident linking rules')
    parser.add_argument('--data-path', type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument('--metrics-path', type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument('--errors-path', type=Path, default=DEFAULT_ERRORS_PATH)
    args = parser.parse_args()
    evaluate_linking(args.data_path, args.metrics_path, args.errors_path)
