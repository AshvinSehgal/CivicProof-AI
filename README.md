# CivicProof AI

CivicProof is a multimodal incident-intelligence platform for municipal
public-works teams. It will combine civic reports, weather alerts, images,
audio, and operational documents to produce evidence-backed triage
recommendations for human approval.

## Current milestone

Milestone 2 adds PostGIS and pgvector-backed incident linking. NYC 311 reports
are stored as geography points, retrieved by bounded distance and time windows,
reranked by semantic similarity, and grouped into auditable incident clusters.

## Quick start

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), and Docker.

```bash
cp .env.example .env
uv sync --extra dev
docker compose up -d postgres redis
uv run uvicorn civicproof.main:app --reload
```

Then open:

- API docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

Run the test suite:

```bash
uv run pytest
```

Rebuild the categorized, balanced, and chronological dataset splits from the
raw NYC 311 snapshots, then evaluate the rules baseline on validation:

```bash
uv run python scripts/build_dataset.py
uv run python scripts/evaluate_baseline.py
```

The evaluation does not read `nyc311_test.json`. Dataset labels are
mapping-derived weak labels, so perfect agreement with the validation mapping
is a regression check rather than proof of real-world generalization. See
[docs/EVALUATION.md](docs/EVALUATION.md) for the current results and limits.

## Initial API

`POST /v1/incidents/triage` accepts a normalized report and returns a
deterministic baseline triage decision. This baseline is deliberately simple:
future multimodal and agentic implementations must beat it in the evaluation
harness rather than merely appear more sophisticated.

Stored incidents and geospatial links can be inspected with:

```text
GET /v1/incidents/{source}/{external_id}
GET /v1/incidents/{source}/{external_id}/nearby?radius_meters=100&hours=24
GET /v1/clusters/{cluster_id}
```

Replaying `scripts/ingest_nyc311.py` populates missing embeddings and links
existing incidents idempotently. See `docs/INCIDENT_LINKING.md` for the scoring
contract and gold-pair evaluation format.

After upgrading a database that already contains incidents, backfill and link
the stored rows without requiring the original source JSON:

```bash
uv run python scripts/link_existing_incidents.py
```

The canonical MVP categories are `pothole`, `fallen_tree`, `flooding`,
`road_obstruction`, and `unknown`. Their operational definitions and mapping
boundaries are documented in [docs/TAXONOMY.md](docs/TAXONOMY.md).

Example:

```bash
curl -X POST http://localhost:8000/v1/incidents/triage \
  -H "Content-Type: application/json" \
  -d '{
    "source": "open311",
    "external_id": "demo-001",
    "description": "Tree blocking the road after a storm",
    "latitude": 42.3601,
    "longitude": -71.0589
  }'
```

## Architecture direction

```text
Open311 / NWS / FEMA / uploads
              |
       ingestion workers
              |
   multimodal normalization
              |
 Postgres + PostGIS + pgvector
              |
 bounded LangGraph workflow
   | evidence | retrieval |
   | risk     | critic    |
              |
 human-reviewed recommendation
              |
 evals, traces, and feedback
```

## Repository layout

```text
src/civicproof/
  api/          HTTP routes
  core/         configuration and cross-cutting concerns
  domain/       typed incident contracts
  services/     application logic and model adapters
tests/          fast unit/API tests
docs/           design decisions and delivery roadmap
scripts/        reproducible dataset and evaluation entry points
```

## Delivery plan

1. Ingest historical NYC or Boston 311 records and live NWS alerts.
2. Add PostGIS storage, idempotent upserts, and temporal/geospatial clustering.
3. Add Hugging Face text classification, VLM, detection, and ASR adapters.
4. Implement hybrid RAG over municipal SOPs and resolved incidents.
5. Orchestrate bounded evidence, retrieval, risk, critic, and approval nodes.
6. Add a golden dataset, baseline comparisons, regression gates, and tracing.

See [docs/ROADMAP.md](docs/ROADMAP.md) for acceptance criteria.
