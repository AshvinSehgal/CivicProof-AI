# Incident Linking Experiment v1

Status: Frozen experimental baseline  
Selected on: 2026-08-20  
Production ready: No

## Problem statement

NYC 311 may receive multiple reports describing the same physical incident.
Treating every report as a separate event creates duplicate alerts, while
incorrectly merging unrelated reports can hide independent incidents.

This experiment evaluates whether spatial distance, temporal distance, category
compatibility, and semantic similarity can identify reports describing the same
event.

## Hypothesis

A hybrid deterministic score combining spatial, temporal, and semantic evidence
will produce fewer false merges than distance-based linking while retaining
useful recall.

## Selection objective

A configuration was eligible when:

- Precision was at least `0.90`.
- False-merge rate was at most `0.10`.
- Human-review rate was at most `0.20`.

Among eligible configurations, recall was maximized. Ties were resolved using
macro category F1, precision, useful review capture, lower review volume, and
overall F1.

## Dataset

The reviewed gold dataset contained 167 incident pairs:

| Split | Pairs | Incidents | Positive pairs | Negative pairs |
|---|---:|---:|---:|---:|
| Calibration | 127 | 100 | 75 | 52 |
| Test | 40 | 67 | 19 | 21 |
| Total | 167 | 167 | 94 | 73 |

The requested calibration ratio was `0.70`. The actual ratio was `0.7605`
because connected incidents were kept together to prevent leakage. A maximum
absolute deviation of `0.07` was allowed for the overall cluster-safe split,
and `0.16` for per-category allocation.

The split used random seed `42`. Pair overlap and incident overlap were both
zero.

Calibration SHA-256:
`c4941f203e1fbe272a1ea0f7227d80c8dd66d0b8ae0b0087498b34d3c0a7d31f`

Test SHA-256:
`6324f524d3380d0d35490a822b763df4eff34b395ae5712f908e5cc754fe3133`

Split-manifest SHA-256:
`42092eea4d3ce428efb3ef045d556abd6cf40316ef2adb829dc37c51e9fd7742`

## Leakage prevention

Pairs were not split independently. A union-find grouping step connected every
pair sharing an incident. Each connected component was assigned entirely to
calibration or test.

This ensured that the same incident could not appear in both splits:

- Incident overlap: `0`
- Pair overlap: `0`

The test split remained hidden during tuning and was evaluated once after the
configuration was frozen.

## Models compared

1. `distance_only`: spatial score only.
2. `distance_time`: weighted spatial and temporal score.
3. `distance_time_category`: spatial and temporal scoring with category
   compatibility.
4. `hybrid_semantic`: spatial, temporal, and embedding-similarity scoring with
   hard distance, time, and category gates.

## Tuning

Tuning used only the calibration split.

The search evaluated:

- Auto-link thresholds: `0.55`, `0.60`, `0.65`, `0.70`, `0.75`
- Review thresholds: `0.55`, `0.60`, `0.65`
- Semantic weights: `0.00`, `0.10`, `0.20`
- Spatial weights: `0.40`, `0.50`, `0.60`
- Temporal weight: `1 - spatial_weight - semantic_weight`

Configurations with a non-positive temporal weight or a review threshold not
below the auto-link threshold were rejected. This produced 81 valid
configurations, of which 43 met the calibration eligibility constraints.

## Selected configuration

| Setting | Value |
|---|---:|
| Configuration version | `v1` |
| Auto-link threshold | `0.70` |
| Review threshold | `0.65` |
| Spatial weight | `0.60` |
| Temporal weight | `0.30` |
| Semantic weight | `0.10` |

Decision policy:

- Score `>= 0.70`: automatically link.
- Score `>= 0.65` and `< 0.70`: preserve for human review.
- Score `< 0.65`: do not link.

When semantic similarity is unavailable, its weight is redistributed
proportionally across the spatial and temporal components.

## Results

| Metric | Calibration | Test |
|---|---:|---:|
| Pairs | 127 | 40 |
| Accuracy | 0.9370 | 0.8250 |
| Precision | 0.9136 | 0.8333 |
| Recall | 0.9867 | 0.7895 |
| F1 | 0.9487 | 0.8108 |
| False-merge rate | 0.0864 | 0.1667 |
| Human-review rate | 0.0079 | 0.0000 |

The calibration configuration satisfied the selection objective. The frozen
test result did not: precision fell below `0.90`, and false-merge rate exceeded
`0.10`.

## Baseline comparison

| Model | Precision | Recall | F1 | False-merge rate |
|---|---:|---:|---:|---:|
| Distance only | 0.7037 | 1.0000 | 0.8261 | 0.2963 |
| Distance and time | 0.6957 | 0.8421 | 0.7619 | 0.3043 |
| Distance, time, and category | 0.8000 | 0.6316 | 0.7059 | 0.2000 |
| Frozen hybrid | 0.8333 | 0.7895 | 0.8108 | 0.1667 |

Distance-only achieved slightly higher F1 on the test split, but its
false-merge rate was substantially worse. It was not selected because model
selection had already been completed on calibration data and because false
merges are the primary safety concern.

## Error analysis

The frozen hybrid model made seven automatic-decision errors:

- Three false-positive links in `unknown`.
- Three false negatives in `unknown`.
- One false negative in `fallen_tree`.

The false-positive `unknown` scores were approximately `0.952`, `0.957`, and
`0.958`. These errors were far above the review boundary, so widening the
ambiguous range would not solve them.

The four false negatives received a score of `0.0` because a hard distance,
time, or category gate rejected them before thresholding.

No hybrid test pairs fell inside the human-review range.

The flooding test slice contained only four negative pairs and no positive
pairs. Its zero precision and recall therefore reflect the absence of positive
support rather than four classification failures.

## Decision

`v1` is frozen as an experimental baseline and is not considered
production-ready. The test set will not be reused for tuning.

## Proposed v2 hypotheses

1. Prevent `unknown` incidents from being automatically linked.
2. Route `unknown` candidates to human review or improve their upstream
   classification.
3. Review the four positive pairs rejected by hard gates.
4. Expand the reviewed dataset, especially flooding and road obstruction.
5. Add category-specific thresholds only after collecting sufficient examples.
6. Create a new independent holdout before evaluating `v2`.

## Reproduction

Build the leakage-safe split:
```bash
uv run python scripts/build_incident_linking_gold_calibration_test.py
```
Tune on calibration data:
```bash
uv run python scripts/tune_incident_linking.py
```
Evaluate the frozen configuration:
```bash
uv run python scripts/evaluate_incident_linking.py \
  --data-path data/incident_linking_test.json \
  --metrics-path artifacts/evaluation/incident_linking_test_metrics_v1.json \
  --errors-path artifacts/evaluation/incident_linking_test_errors_v1.json
```

The final command documents the original evaluation procedure. The existing
test split must not be used for further `v1` tuning.
