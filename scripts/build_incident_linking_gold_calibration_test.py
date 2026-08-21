import json
from pathlib import Path
import random
import argparse

random_seed = 42

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FOLDER = PROJECT_ROOT / 'data'
DATA_PATH = DATA_FOLDER / 'incident_linking_gold.json'
CLUSTER_SPLIT_MANIFEST_PATH = DATA_FOLDER / 'incident_linking_split_manifest.json'
CALIBRATION_PATH = DATA_FOLDER / 'incident_linking_calibration.json'
TEST_PATH = DATA_FOLDER / 'incident_linking_test.json'

calibration_ratio = 0.7
calibration_ratio_tolerance = 0.07
category_ratio_tolerance = 0.16

def find(incident, parent):
    if parent[incident] != incident:
        parent[incident] = find(parent[incident], parent)
    return parent[incident]

def union(first_incident, second_incident, parent):
    first_root = find(first_incident, parent)
    second_root = find(second_incident, parent)
    if first_root != second_root:
        parent[second_root] = first_root

def calculate_split_difference(records, data_categories, target_count, target_positive_count, target_negative_count, target_category_counts, target_cross_category_count):
    positive_count = sum(record['same_event'] for record in records)
    negative_count = len(records) - positive_count
    difference = abs(len(records) - target_count)
    difference += abs(positive_count - target_positive_count)
    difference += abs(negative_count - target_negative_count)
    for category in data_categories:
        category_count = sum(record['category'] == category for record in records)
        difference += abs(category_count - target_category_counts[category])
    cross_category_count = sum(record['category_match'] is False for record in records)
    difference += abs(cross_category_count - target_cross_category_count)
    return difference

def pair_key(record):
    return tuple(sorted((record['incident_a'], record['incident_b'])))

def calculate_distribution(records, data_categories):
    positive_count = sum(record['same_event'] for record in records)
    negative_count = len(records) - positive_count
    category_counts = {}
    for category in data_categories:
        category_counts[category] = sum(record['category'] == category for record in records)
    return {
        'pair_count': len(records),
        'positive_count': positive_count,
        'negative_count': negative_count,
        'positive_ratio': (positive_count / len(records) if len(records) > 0 else 0),
        'cross_category_count': sum(record['category_match'] is False for record in records),
        'category_counts': category_counts
    }

def split_data_clusters(data_path, calibration_path, test_path, cluster_split_manifest_path=CLUSTER_SPLIT_MANIFEST_PATH):
    with open(data_path, 'r') as f:
        data_clusters = json.load(f)
    total_pairs = len(data_clusters)
    data_categories = {record['category'] for record in data_clusters}
    target_count = round(total_pairs * calibration_ratio)
    target_positive_count = round(sum(record['same_event'] for record in data_clusters) * calibration_ratio)
    target_negative_count = round(sum(not record['same_event'] for record in data_clusters) * calibration_ratio)
    target_category_counts = {}
    for category in data_categories:
        target_category_counts[category] = round(sum(record['category'] == category for record in data_clusters) * calibration_ratio)
    target_cross_category_count = round(sum(record['category_match'] is False for record in data_clusters) * calibration_ratio)
    parent = {}
    for pair in data_clusters:
        if pair['incident_a'] not in parent:
            parent[pair['incident_a']] = pair['incident_a']
        if pair['incident_b'] not in parent:
            parent[pair['incident_b']] = pair['incident_b']
        union(pair['incident_a'], pair['incident_b'], parent)
    groups_dict = {}
    for cluster in data_clusters:
        root = find(cluster['incident_a'], parent)
        if root not in groups_dict:
            groups_dict[root] = []
        groups_dict[root].append(cluster)
    calibration_clusters = []
    test_clusters = []
    roots = list(groups_dict.keys())
    random.Random(random_seed).shuffle(roots)
    roots.sort(key=lambda root: len(groups_dict[root]), reverse=True)
    for root in roots:
        added_clusters = (calibration_clusters + groups_dict[root])
        added_difference = calculate_split_difference(added_clusters, data_categories, target_count, target_positive_count, target_negative_count, target_category_counts, target_cross_category_count)
        current_difference = calculate_split_difference(calibration_clusters, data_categories, target_count, target_positive_count, target_negative_count, target_category_counts, target_cross_category_count)
        if added_difference <= current_difference:
            calibration_clusters.extend(groups_dict[root])
        else:
            test_clusters.extend(groups_dict[root])

    calibration_incidents = {incident for record in calibration_clusters for incident in (record['incident_a'], record['incident_b'])}
    test_incidents = {incident for record in test_clusters for incident in (record['incident_a'], record['incident_b'])}
    assert calibration_incidents.isdisjoint(test_incidents)
    assert len(calibration_clusters) + len(test_clusters) == total_pairs
    assert len(calibration_incidents) > 0
    assert len(test_incidents) > 0

    calibration_pairs = {pair_key(record) for record in calibration_clusters}
    test_pairs = {pair_key(record) for record in test_clusters}
    assert calibration_pairs.isdisjoint(test_pairs)
    assert calibration_pairs | test_pairs == {pair_key(record) for record in data_clusters}
    
    pair_overlap_count = len(calibration_pairs & test_pairs)
    incident_overlap_count = len(calibration_incidents & test_incidents)
    assert pair_overlap_count == 0
    assert incident_overlap_count == 0

    calibration_categories = {record['category'] for record in calibration_clusters}
    test_categories = {record['category'] for record in test_clusters}
    assert calibration_categories == data_categories
    assert test_categories == data_categories
    assert abs(len(calibration_clusters) / total_pairs - calibration_ratio) <= calibration_ratio_tolerance

    assert {record['same_event'] for record in calibration_clusters} == {False, True}
    assert {record['same_event'] for record in test_clusters} == {False, True}

    assert any(record['category_match'] is False for record in calibration_clusters)
    assert any(record['category_match'] is False for record in test_clusters)
    
    data_distribution = calculate_distribution(data_clusters, data_categories)
    calibration_distribution = calculate_distribution(calibration_clusters, data_categories)
    test_distribution = calculate_distribution(test_clusters, data_categories)
    
    data_positive_ratio = data_distribution['positive_ratio']
    calibration_positive_ratio = calibration_distribution['positive_ratio']
    test_positive_ratio = test_distribution['positive_ratio']
    assert abs(calibration_positive_ratio - data_positive_ratio) <= 0.10
    assert abs(test_positive_ratio - data_positive_ratio) <= 0.10
    for category in data_categories:
        data_category_count = data_distribution['category_counts'][category]
        calibration_category_count = calibration_distribution['category_counts'][category]
        assigned_ratio = (calibration_category_count / data_category_count)
        assert abs(assigned_ratio - calibration_ratio) <= category_ratio_tolerance, f'{category} calibration ratio was {assigned_ratio}'

    with open(cluster_split_manifest_path, 'w') as f:
        json.dump({
            'seed': random_seed,
            'calibration_ratio': calibration_ratio,
            'calibration_ratio_tolerance': calibration_ratio_tolerance,
            'category_ratio_tolerance': category_ratio_tolerance,
            'actual_calibration_ratio': len(calibration_clusters) / total_pairs,
            'gold_pair_count': len(data_clusters),
            'calibration_pair_count': len(calibration_clusters),
            'test_pair_count': len(test_clusters),
            'calibration_incident_count': len(calibration_incidents),
            'test_incident_count': len(test_incidents),
            'incident_overlap_count': 0,
            'pair_overlap_count': 0,
            'gold_distribution': data_distribution,
            'calibration_distribution': calibration_distribution,
            'test_distribution': test_distribution
        }, 
        f, indent=2)

    with open(calibration_path, 'w') as f:
        json.dump(calibration_clusters, f, indent=2)
    with open(test_path, 'w') as f:
        json.dump(test_clusters, f, indent=2)
    
    print('Successfully split the dataset of clusters.')
    print('Data pairs:', len(data_clusters))
    print('Calibration + test pairs:', len(calibration_clusters) + len(test_clusters))
    print('Pair overlap:', pair_overlap_count)
    print('Incident overlap:', incident_overlap_count)
    print('Calibration categories:', calibration_categories)
    print('Test categories:', test_categories)
    print('Both labels in calibration:', {record['same_event'] for record in calibration_clusters})
    print('Both labels in test:', {record['same_event'] for record in test_clusters})

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Split incident clusters into calibration and test sets')
    parser.add_argument('--data-path', type=Path, default=DATA_PATH)
    parser.add_argument('--calibration-path', type=Path, default=CALIBRATION_PATH)
    parser.add_argument('--test-path', type=Path, default=TEST_PATH)
    parser.add_argument('--cluster-split-manifest-path', type=Path, default=CLUSTER_SPLIT_MANIFEST_PATH)
    args = parser.parse_args()
    split_data_clusters(args.data_path, args.calibration_path, args.test_path, args.cluster_split_manifest_path)
