INCIDENT_LINKING_CONFIG_VERSION = 'v1'
INCIDENT_LINKING_SELECTED_ON = '2026-08-20'

AUTO_LINK_THRESHOLD = 0.70
REVIEW_THRESHOLD = 0.65

SPATIAL_WEIGHT = 0.60
TEMPORAL_WEIGHT = 0.30
SEMANTIC_WEIGHT = 0.10

LINKING_RULES = {
    'pothole': {'radius_meters': 50.0, 'hours': 72},
    'fallen_tree': {'radius_meters': 100.0, 'hours': 48},
    'flooding': {'radius_meters': 300.0, 'hours': 24},
    'road_obstruction': {'radius_meters': 150.0, 'hours': 24},
    'unknown': {'radius_meters': 50.0, 'hours': 12}
}

CALIBRATION_SUMMARY = {
    'data_file': 'incident_linking_calibration.json',
    'data_sha256': 'c4941f203e1fbe272a1ea0f7227d80c8dd66d0b8ae0b0087498b34d3c0a7d31f',
    'split_manifest_sha256': '42092eea4d3ce428efb3ef045d556abd6cf40316ef2adb829dc37c51e9fd7742',
    'record_count': 127,
    'precision': 0.9135802469135802,
    'recall': 0.9866666666666667,
    'f1': 0.9487179487179487,
    'false_merge_rate': 0.08641975308641975,
    'human_review_rate': 0.007874015748031496
}

TEST_SUMMARY = {
    'data_file': 'incident_linking_test.json',
    'data_sha256': '6324f524d3380d0d35490a822b763df4eff34b395ae5712f908e5cc754fe3133',
    'record_count': 40,
    'precision': 0.8333333333333334,
    'recall': 0.7894736842105263,
    'f1': 0.8108108108108109,
    'false_merge_rate': 0.16666666666666666,
    'human_review_rate': 0.0,
    'meets_selection_constraints': False
}
