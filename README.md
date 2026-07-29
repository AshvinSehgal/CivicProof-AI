# CivicProof AI

CivicProof is a multimodal incident-intelligence platform for municipal
public-works teams. It will combine civic reports, weather alerts, images,
audio, and operational documents to produce evidence-backed triage
recommendations for human approval.

## Current milestone

Milestone 0 establishes a small, testable FastAPI service and the domain
contract used by later ingestion, retrieval, and LangGraph workflows.

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

## Initial API

`POST /v1/incidents/triage` accepts a normalized report and returns a
deterministic baseline triage decision. This baseline is deliberately simple:
future multimodal and agentic implementations must beat it in the evaluation
harness rather than merely appear more sophisticated.

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
```

## Delivery plan

1. Ingest historical NYC or Boston 311 records and live NWS alerts.
2. Add PostGIS storage, idempotent upserts, and temporal/geospatial clustering.
3. Add Hugging Face text classification, VLM, detection, and ASR adapters.
4. Implement hybrid RAG over municipal SOPs and resolved incidents.
5. Orchestrate bounded evidence, retrieval, risk, critic, and approval nodes.
6. Add a golden dataset, baseline comparisons, regression gates, and tracing.

See [docs/ROADMAP.md](docs/ROADMAP.md) for acceptance criteria.
