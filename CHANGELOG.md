# Changelog

## v1.0-beta1 · Business Runtime Verification Candidate

- Added signed, environment-bound, freshness-limited **Business E2E Certification**.
- Added authenticated Coach → Writer → Reviewer → Evidence Verification → Critic/Revision business-path certification.
- Expanded cross-tenant attack certification across session, workflow, evidence, evidence graph, feedback, artifacts, artifact trace and private-file access.
- Certification identities now use unique ephemeral random credentials and are de-identified/archived after each run.
- Added Semantic RAG quality gate with current-year/authority checks and cross-tenant knowledge-leak detection.
- Runtime background-job certification now requires a separately running worker process; the certifier no longer calls `work_once()` itself.
- Added Redis stale-lease recovery foundation, independent worker completion proof, heartbeat/running-set metadata and recovery probe.
- S3-compatible certification now performs a real presigned-URL HTTP GET and verifies content SHA256 before cleanup.
- Added realistic SQLite→PostgreSQL migration certification using a disposable PostgreSQL database.
- Added PostgreSQL backup/restore certification using a disposable schema and `pg_dump`/`pg_restore`.
- Added measured staging load-smoke certification; explicitly not a 100/500/1000 concurrency capacity claim.
- Added observability sink health certification hook; event-ingestion verification remains a future hardening item.
- Production `/ready` now requires both a valid runtime certificate and a valid business E2E certificate.
- Runtime certification model configuration now uses the selected `RepositoryContainer` backend rather than bypassing PostgreSQL with a local SQLite model store.
- Worker startup remains decoupled from FastAPI `app.main` and shares job-handler registration through `app/job_handlers.py`.
- Added beta1 staging preflight/gate updates and CI-compatible regression coverage.
- No new schema tables or Alembic revision were introduced; Alembic head remains `0007_tenant_templates_evidence_risk`.
- Regression baseline: **132 tests passed** in isolated groups; live external runtime remains `NOT VERIFIED` in the build environment.

## v1.0-beta0 · Runtime Certification Candidate

- Added signed, environment-bound and freshness-limited runtime certification v2.
- Added live pgvector, distributed Redis limiter and Redis job round-trip certification probes.
- Added PostgreSQL+pgvector+Redis+MinIO+API+worker+certifier staging Compose harness.
- Decoupled worker startup from FastAPI `app.main`.
- Runtime certification reads model configuration through the selected RepositoryContainer backend.
- Added staging preflight, staging runtime gate and CI regression workflow.
