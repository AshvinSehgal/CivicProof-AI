import argparse
import json
from pathlib import Path
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support
from civicproof.core.incident_linking_config import AUTO_LINK_THRESHOLD, INCIDENT_LINKING_CONFIG_VERSION, LINKING_RULES, REVIEW_THRESHOLD, SEMANTIC_WEIGHT, SPATIAL_WEIGHT, TEMPORAL_WEIGHT

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / 'data' / 'incident_linking_calibration.json'
DEFAULT_METRICS_PATH = PROJECT_ROOT / 'artifacts' / 'evaluation' / 'incident_linking_metrics.json'
DEFAULT_ERRORS_PATH = PROJECT_ROOT / 'artifacts' / 'evaluation' / 'incident_linking_errors.json'
DEFAULT_REVIEW_THRESHOLD = REVIEW_THRESHOLD

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

def calculate_review_metrics(labels, prediction_results):
    decisions = [prediction_result['decision'] for prediction_result in prediction_results]
    auto_link_count = decisions.count('auto_link')
    human_review_count = decisions.count('human_review')
    no_link_count = decisions.count('no_link')
    human_review_same_event_count = sum(labels[index] and decisions[index] == 'human_review' for index in range(len(labels)))
    human_review_different_event_count = sum(not labels[index] and decisions[index] == 'human_review' for index in range(len(labels)))
    return {
        'auto_link_count': auto_link_count,
        'human_review_count': human_review_count,
        'no_link_count': no_link_count,
        'human_review_rate': human_review_count / len(labels) if len(labels) > 0 else 0,
        'automatic_decision_rate': (auto_link_count + no_link_count) / len(labels) if len(labels) > 0 else 0,
        'human_review_same_event_count': human_review_same_event_count,
        'human_review_different_event_count': human_review_different_event_count
    }

def predict_pair(record, model_name, linking_config=None):
    category = record['category']
    if linking_config is not None:
        category_radii = linking_config['category_radii'][category]
        category_time_window = linking_config['category_time_windows'][category]
        auto_link_threshold = linking_config['threshold']
        review_threshold = linking_config['review_threshold']
    else:
        category_radii = LINKING_RULES[category]['radius_meters']
        category_time_window = LINKING_RULES[category]['hours'] * 60 * 60
        auto_link_threshold = AUTO_LINK_THRESHOLD
        review_threshold = DEFAULT_REVIEW_THRESHOLD
    if review_threshold >= auto_link_threshold:
        raise ValueError('review threshold must be lower than auto-link threshold')
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
            spatial_weight = SPATIAL_WEIGHT
            semantic_weight = SEMANTIC_WEIGHT
            temporal_weight = TEMPORAL_WEIGHT
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
    if score >= auto_link_threshold:
        decision = 'auto_link'
    elif score >= review_threshold:
        decision = 'human_review'
    else:
        decision = 'no_link'
    return {
        'score': score,
        'prediction': decision == 'auto_link',
        'within_radius': within_radius,
        'within_time_window': within_time_window,
        'category_match': category_match,
        'decision': decision,
        'auto_link_threshold': auto_link_threshold,
        'review_threshold': review_threshold
    }

def evaluate_linking(data_path, metrics_path, errors_path):
    with open(data_path, 'r') as f:
        records = json.load(f)
    labels = [record['same_event'] for record in records]
    model_names = ['distance_only', 'distance_time', 'distance_time_category', 'hybrid_semantic']
    metrics = {
        'config_version': INCIDENT_LINKING_CONFIG_VERSION,
        'auto_link_threshold': AUTO_LINK_THRESHOLD,
        'review_threshold': DEFAULT_REVIEW_THRESHOLD,
        'models': {}
    }
    model_errors = []
    human_review_cases = []
    categories = sorted({record['category'] for record in records})
    for model_name in model_names:
        prediction_results = [predict_pair(record, model_name) for record in records]
        predictions = [prediction_result['decision'] == 'auto_link' for prediction_result in prediction_results]
        metrics['models'][model_name] = {
            'overall': calculate_metrics(labels, predictions),
            'by_category': {}
        }
        metrics['models'][model_name]['overall'].update(calculate_review_metrics(labels, prediction_results))
        for category in categories:
            category_indexes = [index for index in range(len(records)) if records[index]['category'] == category]
            category_labels = [labels[index] for index in category_indexes]
            category_predictions = [predictions[index] for index in category_indexes]
            category_prediction_results = [prediction_results[index] for index in category_indexes]
            metrics['models'][model_name]['by_category'][category] = calculate_metrics(category_labels, category_predictions)
            metrics['models'][model_name]['by_category'][category].update(calculate_review_metrics(category_labels, category_prediction_results))
        for index in range(len(records)):
            record = records[index]
            prediction_result = prediction_results[index]
            if prediction_result['decision'] == 'human_review':
                human_review_cases.append({
                    'model_name': model_name,
                    'incident_a': record['incident_a'],
                    'incident_b': record['incident_b'],
                    'category': record['category'],
                    'expected': labels[index],
                    'score': prediction_result['score'],
                    'decision': prediction_result['decision'],
                    'distance_meters': record['distance_meters'],
                    'time_difference_seconds': record['time_difference_seconds'],
                    'semantic_similarity': record.get('semantic_similarity'),
                    'review_rationale': record.get('review_rationale')
                })
            if prediction_result['decision'] != 'human_review' and predictions[index] != labels[index]:
                model_errors.append({
                    'model_name': model_name,
                    'incident_a': record['incident_a'],
                    'incident_b': record['incident_b'],
                    'category': record['category'],
                    'expected': labels[index],
                    'predicted': predictions[index],
                    'error_type': 'false_positive' if predictions[index] else 'false_negative',
                    'score': prediction_result['score'],
                    'decision': prediction_result['decision'],
                    'distance_meters': record['distance_meters'],
                    'time_difference_seconds': record['time_difference_seconds'],
                    'semantic_similarity': record.get('semantic_similarity'),
                    'within_radius': prediction_result['within_radius'],
                    'within_time_window': prediction_result['within_time_window'],
                    'category_match': prediction_result['category_match'],
                    'review_rationale': record.get('review_rationale')
                })
    highest_f1_model = max(metrics['models'], key=lambda model_name: metrics['models'][model_name]['overall']['f1'])
    metrics['selected_model'] = 'hybrid_semantic'
    metrics['highest_f1_model_for_reference'] = highest_f1_model
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    errors_path.parent.mkdir(parents=True, exist_ok=True)
    with open(errors_path, 'w') as f:
        json.dump({
            'data_file': data_path.name,
            'config_version': INCIDENT_LINKING_CONFIG_VERSION,
            'auto_link_threshold': AUTO_LINK_THRESHOLD,
            'review_threshold': DEFAULT_REVIEW_THRESHOLD,
            'error_count': len(model_errors),
            'errors': model_errors,
            'human_review_count': len(human_review_cases),
            'human_review_cases': human_review_cases
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
