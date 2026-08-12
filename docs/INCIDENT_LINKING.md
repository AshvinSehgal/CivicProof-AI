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
5. The highest deterministic score above `0.55` joins the report to a cluster.
6. If no candidate qualifies, the report becomes the anchor of a new cluster.

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
