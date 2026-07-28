# CareerOS Changelog

## v1.6-ui-i18n

- Added global zh-CN / en-US hot switching with persisted browser preference and localized Coach replies.
- Completed user plan submission, artifact directory/version timeline, diff/restore/export actions, score radar, and retryable task states.
- Added advisor-side real review execution, evidence-grounded recommendation routing, progress drill-down, and feedback persistence.
- Added tenant workflow/artifact template configuration and server-authoritative RBAC assignment UI.
- Removed the Showcase catch-all “页面建设中” placeholder and retained an explicit Demo Scenario boundary.
- Regression baseline: 167 tests passed; external model and production certification remain separate gates.

## 1.5.0-domain-intelligence

See `CHANGELOG_v1.5.md`. Claim → Capability → Requirement → Gap is now a persistent, versioned, explainable and auditable server-side domain.

# CareerOS v1.4

See `CHANGELOG_v1.4.md` for the canonical runtime release changes.

# Changelog

## v1.2-beta · Domain Closure & Open API Gateway Candidate

- Added H5 State Schema v2 and state-driven Evidence → Capability → Job Requirement → Match/Gap → Task derivation.
- Normalized locally generated tasks with stable IDs and origin metadata; removed legacy incomplete task creation path.
- Added LocalDemoAdapter / ApiAdapter foundation and runtime mode switching in H5 settings.
- Extended provider kinds with `custom_rest` and vendor-neutral connection metadata without a database-table migration.
- Added generic auth modes including OAuth2 Client Credentials, configurable chat/models paths, request templates, response mapping, query parameters, and model discovery.
- Added real backend Provider Playground endpoint and UI for direct provider invocation with latency/usage output.
- Added real Provider connection tests; offline Showcase no longer reports fake connectivity.
- Added RFC4180-style CSV parsing, backup restore with schema envelope, default-workspace activation, and dependency-aware Evidence deletion warnings.
- Replaced active fixed Showcase KPI/score values with state-derived dashboards and explicit `Not reviewed`/unverified states.
- Replaced fabricated local retrieval probability-like scores with transparent matched-term output.
- Added v1.2 regression tests for Custom REST persistence, secret masking, template rendering, response mapping and actual mock HTTP execution.
- Production status remains **NOT VERIFIED** until real PostgreSQL/pgvector, Redis, object storage, semantic embedding, external model providers and certification gates pass in the target environment.


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

## 2026-07-23 · H5 Showcase v1.1 interaction closure

- Added 10-language global UI selector with persisted locale and Arabic RTL support.
- Converted H5 showcase controls from toast-only responses into persistent local CRUD/action loops.
- Added artifact versioning/restore/duplicate/delete/export flows.
- Added Evidence, task, user, PPT, interview, knowledge, job-data, provider, notification, analytics, usage, and settings closure flows.
- Corrected offline Provider status from misleading `Connected` labels to `Demo / Unverified`.
- Added browser-level regression coverage and route-language smoke verification.
- Kept production capability boundaries explicit: no fake external AI/database/object-storage connectivity.
