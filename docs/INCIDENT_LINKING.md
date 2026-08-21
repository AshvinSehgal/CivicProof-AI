# Incident linking

Incident linking treats PostGIS proximity search as candidate retrieval, not as
proof that two reports describe the same event. Candidates must share a
category and are scored using distance, time, and semantic similarity.

## Flow

1. Ingestion normalizes coordinates and creates a PostGIS geography point.
2. The BGE model creates a normalized 384-dimensional incident embedding.
3. `ST_DWithin` retrieves category-compatible reports inside the configured
   distance and time window.
4. pgvector cosine similarity reranks the bounded candidate set.
5. The highest deterministic score at or above `0.70` joins the report to a cluster.
6. A score from `0.65` up to `0.70` creates a separate cluster and preserves the candidate evidence for human review.
7. If no candidate qualifies, the report becomes the anchor of a new cluster.

## Frozen configuration

The production incident-linking configuration is frozen as `v1` in
`core/incident_linking_config.py`. Production linking and offline evaluation
both import the same thresholds, weights, and category rules from this file.

The `v1` configuration uses spatial weight `0.60`, temporal weight `0.30`, and
semantic weight `0.10`. The configuration file records the calibration and test
dataset hashes and final metrics so the evaluation can be reproduced without
committing the reviewed datasets.

The test split is a holdout and must not be used to modify `v1`. Any later
configuration change must create a new version and use new independent test
data.

The frozen hybrid model achieved test precision `0.8333`, recall `0.7895`, F1
`0.8108`, and false-merge rate `0.1667`. This does not meet the calibration
selection constraints, so `v1` is retained as an immutable evaluation baseline
rather than treated as production-ready policy.

The distance and time windows are initial hypotheses in
`services/incident_linking.py`. They must be calibrated against reviewed pairs
before being treated as production policy.

## Evaluation data

Create `data/incident_linking_gold.json` as a JSON array. Each reviewed pair
uses this shape:

```json
{
  "incident_a": "open311:123",
  "incident_b": "open311:456",
  "category": "flooding",
  "category_match": true,
  "distance_meters": 42.3,
  "time_difference_seconds": 1800,
  "semantic_similarity": 0.82,
  "same_event": true
}
```

Run:

```bash
uv run python scripts/evaluate_incident_linking.py
```

The evaluator compares distance-only, distance-plus-time,
distance-time-category, and hybrid semantic linking. Review false merges first;
for operational incidents, link precision is the initial safety priority.

## Existing database backfill

After applying the migrations, populate embeddings and clusters for rows that
were ingested before incident linking existed:

```bash
uv run python scripts/link_existing_incidents.py
```

The script only generates missing embeddings, reuses existing memberships, and
commits in batches. It is safe to resume after interruption.

Detailed experiment report: [Incident Linking v1](experiments/incident_linking_v1.md)