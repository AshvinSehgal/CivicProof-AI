import json
from pathlib import Path
import runpy

PROJECT_ROOT = Path(__file__).resolve().parents[1]
split_script = runpy.run_path(PROJECT_ROOT / 'scripts' / 'build_incident_linking_gold_calibration_test.py')
DATA_PATH = split_script['DATA_PATH']
pair_key = split_script['pair_key']
split_data_clusters = split_script['split_data_clusters']

def test_calibration_test_sets_dont_overlap(tmp_path):
    testing_data_path = tmp_path / 'incident_linking_gold.json'
    testing_calibration_path = tmp_path / 'incident_linking_calibration.json'
    testing_test_path = tmp_path / 'incident_linking_test.json'
    testing_manifest_path = tmp_path / 'incident_linking_split_manifest.json'
    with open(DATA_PATH, 'r') as f:
        data = json.load(f)
    with open(testing_data_path, 'w') as f:
        json.dump(data, f, indent=2)
    split_data_clusters(testing_data_path, testing_calibration_path, testing_test_path, testing_manifest_path)
    with open(testing_calibration_path, 'r') as f:
        calibration_data = json.load(f)
    with open(testing_test_path, 'r') as f:
        test_data = json.load(f)
    with open(testing_manifest_path, 'r') as f:
        manifest = json.load(f)
    calibration_incidents = {incident for record in calibration_data for incident in (record['incident_a'], record['incident_b'])}
    test_incidents = {incident for record in test_data for incident in (record['incident_a'], record['incident_b'])}
    calibration_pairs = {pair_key(record) for record in calibration_data}
    test_pairs = {pair_key(record) for record in test_data}
    assert calibration_incidents.isdisjoint(test_incidents)
    assert calibration_pairs.isdisjoint(test_pairs)
    assert calibration_pairs | test_pairs == {pair_key(record) for record in data}
    assert len(calibration_data) + len(test_data) == len(data)
    assert manifest['incident_overlap_count'] == 0
    assert manifest['pair_overlap_count'] == 0
