import argparse
from pathlib import Path
import json
import itertools
from evaluate_incident_linking import predict_pair, calculate_metrics
from civicproof.services.incident_linking import LINKING_RULES

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / 'data' / 'incident_linking_calibration.json'
DEFAULT_METRICS_PATH = PROJECT_ROOT / 'artifacts' / 'evaluation' / 'incident_linking_tuning_metrics.json'
DEFAULT_ERRORS_PATH = PROJECT_ROOT / 'artifacts' / 'evaluation' / 'incident_linking_tuning_errors.json'

THRESHOLDS = [0.55, 0.60, 0.65, 0.70, 0.75]
SEMANTIC_WEIGHTS = [0.00, 0.10, 0.20]
SPATIAL_WEIGHTS = [0.40, 0.50, 0.60]

PRECISION_THRESHOLD = 0.9
FALSE_MERGE_RATE_THRESHOLD = 0.1

def tune_incident_linking(records, data_path, metrics_path, errors_path):
    model_name = 'hybrid_semantic'
    labels = [record['same_event'] for record in records]
    categories = sorted({record['category'] for record in records})
    tuning_results = []
    eligible_results = []
    for (threshold, semantic_weight, spatial_weight) in itertools.product(THRESHOLDS, SEMANTIC_WEIGHTS, SPATIAL_WEIGHTS):
        temporal_weight = round(1 - semantic_weight - spatial_weight, 2)
        if temporal_weight <= 0:
            continue
        linking_config = {
            'threshold': threshold,
            'spatial_weight': spatial_weight,
            'semantic_weight': semantic_weight,
            'temporal_weight': temporal_weight,
            'category_radii': {category: LINKING_RULES[category]['radius_meters'] for category in LINKING_RULES},
            'category_time_windows': {category: LINKING_RULES[category]['hours'] * 60 * 60 for category in LINKING_RULES}
        }
        metrics = {
            'threshold': threshold,
            'spatial_weight': spatial_weight,
            'semantic_weight': semantic_weight,
            'temporal_weight': temporal_weight
        }
        prediction_results = [predict_pair(record, model_name, linking_config) for record in records]
        predictions = [prediction_result['prediction'] for prediction_result in prediction_results]
        result_metrics = calculate_metrics(labels, predictions)
        metrics['overall'] = result_metrics
        metrics['by_category'] = {}
        for category in categories:
            category_labels = [labels[index] for index in range(len(records)) if records[index]['category'] == category]
            category_predictions = [predictions[index] for index in range(len(records)) if records[index]['category'] == category]
            metrics['by_category'][category] = calculate_metrics(category_labels, category_predictions)
        metrics['macro_category_f1'] = sum(metrics['by_category'][category]['f1'] for category in categories) / len(categories)
        metrics['worst_category_recall'] = min(metrics['by_category'][category]['recall'] for category in categories)
        metrics['eligible'] = result_metrics['precision'] >= PRECISION_THRESHOLD and result_metrics['false_merge_rate'] <= FALSE_MERGE_RATE_THRESHOLD
        tuning_results.append(metrics)
        if result_metrics['precision'] >= PRECISION_THRESHOLD and result_metrics['false_merge_rate'] <= FALSE_MERGE_RATE_THRESHOLD:
            eligible_results.append(metrics)
    if len(eligible_results) == 0:
        raise ValueError('No tuning configuration met the model-selection constraints')
    best_result = max(eligible_results, key=lambda result: (result['overall']['recall'], result['macro_category_f1'], result['overall']['precision'], result['overall']['f1']))
    best_config = {
        'threshold': best_result['threshold'],
        'spatial_weight': best_result['spatial_weight'],
        'semantic_weight': best_result['semantic_weight'],
        'temporal_weight': best_result['temporal_weight'],
        'category_radii': {category: LINKING_RULES[category]['radius_meters'] for category in LINKING_RULES},
        'category_time_windows': {category: LINKING_RULES[category]['hours'] * 60 * 60 for category in LINKING_RULES}
    }
    best_prediction_results = [predict_pair(record, model_name, best_config) for record in records]
    best_predictions = [prediction_result['prediction'] for prediction_result in best_prediction_results]
    model_errors = []
    for index in range(len(records)):
        if best_predictions[index] != labels[index]:
            record = records[index]
            prediction_result = best_prediction_results[index]
            model_errors.append({
                'incident_a': record['incident_a'],
                'incident_b': record['incident_b'],
                'category': record['category'],
                'expected': labels[index],
                'predicted': best_predictions[index],
                'error_type': 'false_positive' if best_predictions[index] else 'false_negative',
                'score': prediction_result['score'],
                'distance_meters': record['distance_meters'],
                'time_difference_seconds': record['time_difference_seconds'],
                'semantic_similarity': record.get('semantic_similarity'),
                'within_radius': prediction_result['within_radius'],
                'within_time_window': prediction_result['within_time_window'],
                'category_match': prediction_result['category_match'],
                'review_rationale': record.get('review_rationale')
            })
    tuning_metrics = {
        'data_file': data_path.name,
        'selection_objective': {
            'minimum_precision': PRECISION_THRESHOLD,
            'maximum_false_merge_rate': FALSE_MERGE_RATE_THRESHOLD,
            'optimize': 'recall',
            'first_tie_breaker': 'macro_category_f1',
            'second_tie_breaker': 'precision',
            'third_tie_breaker': 'f1'
        },
        'configuration_count': len(tuning_results),
        'eligible_configuration_count': len(eligible_results),
        'best_configuration': best_result,
        'configurations': tuning_results
    }
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metrics_path, 'w') as f:
        json.dump(tuning_metrics, f, indent=2)
    errors_path.parent.mkdir(parents=True, exist_ok=True)
    with open(errors_path, 'w') as f:
        json.dump({
            'data_file': data_path.name,
            'best_configuration': best_config,
            'error_count': len(model_errors),
            'errors': model_errors
        }, f, indent=2)
    print(json.dumps(tuning_metrics['best_configuration'], indent=2))
    print('Tuning metrics:', metrics_path)
    print('Model errors:', errors_path)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Evaluate incident linking rules')
    parser.add_argument('--data-path', type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument('--metrics-path', type=Path, default=DEFAULT_METRICS_PATH)
    parser.add_argument('--errors-path', type=Path, default=DEFAULT_ERRORS_PATH)
    args = parser.parse_args()
    with open(args.data_path, 'r') as f:
        records = json.load(f)
    tune_incident_linking(records, args.data_path, args.metrics_path, args.errors_path)
