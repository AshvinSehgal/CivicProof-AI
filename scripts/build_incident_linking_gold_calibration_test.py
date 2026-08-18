import json
from pathlib import Path
import json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_FOLDER = PROJECT_ROOT / 'data'
GOLD_REVIEWS_PATH = DATA_FOLDER / 'incident_linking_gold.json'
CALIBRATION_REVIEWS_PATH = DATA_FOLDER / 'incident_linking_calibration.json'
TEST_REVIEWS_PATH = DATA_FOLDER / 'incident_linking_test.json'

with open(GOLD_REVIEWS_PATH, 'r') as f:
    CLUSTER_REVIEWS = json.load(f)

parent = {}

def find(incident):
    if parent[incident] != incident:
        parent[incident] = find(parent[incident])
    return parent[incident]

def union(first_incident, second_incident):
    first_root = find(first_incident)
    second_root = find(second_incident)
    if first_root != second_root:
        parent[second_root] = first_root

for pair in CLUSTER_REVIEWS:
    parent[pair['incident_b']] = pair['incident_a']
    parent[pair['incident_a']] = ''
    root = union(pair['incident_a'], pair['incident_b'])
print(parent)
exit(0)

calibration_size = int(0.7 * len(CLUSTER_REVIEWS))
calibration_data = CLUSTER_REVIEWS[:calibration_size]
test_data = CLUSTER_REVIEWS[calibration_size:]

with open(CALIBRATION_REVIEWS_PATH, 'w') as f:
    json.dump(calibration_data, f, indent=2)
with open(TEST_REVIEWS_PATH, 'w') as f:
    json.dump(test_data, f, indent=2)