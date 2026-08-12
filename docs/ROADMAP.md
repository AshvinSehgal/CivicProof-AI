# CivicProof delivery roadmap

## Product boundary

The first release supports one city and four public-works categories:
flooding, fallen trees, potholes, and road obstructions. It recommends actions
but cannot dispatch crews or submit government service requests.

## Milestone 0 — Foundation

- [x] Typed FastAPI service
- [x] Transparent rules baseline
- [x] Health and triage endpoints
- [x] Unit/API tests
- [x] Local PostgreSQL/pgvector and Redis services

Exit criterion: a new contributor can run the API and tests locally.

## Milestone 1 — Real data

- [ ] Select NYC or Boston as the first jurisdiction
- [ ] Ingest a bounded historical 311 sample
- [ ] Ingest active National Weather Service alerts
- [ ] Add SQLAlchemy models and Alembic migrations
- [ ] Implement idempotent source-aware upserts
- [ ] Record raw payload lineage and ingestion failures

Exit criterion: replaying an ingestion window creates no duplicate records.

## Milestone 2 — Retrieval and incident linking

- [x] Enable PostGIS and pgvector extensions
- [x] Cluster reports by time, distance, and semantic similarity
- [ ] Index municipal SOP documents with hybrid retrieval
- [ ] Add a reranker and citation-preserving context contract
- [ ] Measure Recall@5 and nDCG@10 against labeled queries

Exit criterion: retrieval beats keyword-only and dense-only baselines.

## Milestone 3 — Multimodal evidence

- [ ] Image-text-to-text adapter
- [ ] Zero-shot object detection adapter
- [ ] Automatic speech recognition adapter
- [ ] Model router with timeouts, retries, and fallbacks
- [ ] Persist model identity, version, latency, and confidence

Exit criterion: every prediction is traceable and the system safely abstains
when evidence is missing or contradictory.

## Milestone 4 — Bounded orchestration

- [ ] Evidence node
- [ ] Retrieval node
- [ ] Risk node
- [ ] Critic node
- [ ] Human approval interrupt
- [ ] Checkpointed and replayable LangGraph state

Exit criterion: agent runs are deterministic at workflow boundaries and no
external action occurs without approval.

## Milestone 5 — Evaluation and operations

- [ ] Versioned golden dataset
- [ ] Rules, single-model, and graph baselines
- [ ] Adversarial and prompt-injection cases
- [ ] CI regression thresholds
- [ ] OpenTelemetry traces and operational dashboards
- [ ] Cost, latency, calibration, and correction-rate reporting

Exit criterion: a model or prompt change cannot ship when it regresses a
declared quality gate.

## First engineering decision

Use PostgreSQL with PostGIS and pgvector for the initial release. It supports
transactional, geospatial, full-text, and vector queries without adding a
second persistence service. Reconsider a dedicated vector database only after
measured load or isolation requirements justify it.
