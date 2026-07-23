# Architecture Debt Audit · CareerOS v1.0-alpha8

## Current measurements

- `app/main.py`: 2,159 lines at release audit time.
- Route decorators across `app/main.py` + modular routers: approximately 139.
- Repository contract pairs: 12/12, 0 missing public methods.
- Direct SQLite modules: 13 total; 12 business compatibility modules; 0 unexpected modules.
- Store-owned DDL violations: 0.
- Schema ownership status: `CENTRALIZED`.
- Alembic head: `0007_tenant_templates_evidence_risk`.
- Schema manifest: 44 business tables.

## Debt reduced in alpha8

1. Tenant configuration no longer depends only on built-in Python workflow/artifact definitions.
2. New tenant template persistence uses SQLAlchemy and does not introduce a new direct `sqlite3` business module.
3. High-risk factual claims have explicit governance metadata and human-review requirements.
4. Background jobs now have idempotency, lease/heartbeat and dead-letter foundations.
5. Template administration routes moved out of the application composition root.

## Debt still open

### P0 before runtime-verified beta

- Live PostgreSQL + pgvector certification.
- Live SQLite-to-PostgreSQL migration drill.
- Live Redis multi-instance rate-limit and worker recovery tests.
- Live S3/R2/MinIO private-object round trip.
- Real semantic embedding + generation LLM E2E.
- Live observability backend and PostgreSQL restore drill.
- Staging load tests at measured concurrency levels.

### P1 architecture debt

- Continue moving routers out of `app/main.py` until it is primarily an app factory/composition root.
- Gradually replace direct SQLite CRUD compatibility stores with repository-only access while preserving local SQLite mode.
- Move tenant workflow/artifact configuration toward richer rule/schema validation and an administrator builder.
- Add production-grade entailment/NLI verification and human-review workflow for evidence claims.
- Strengthen Redis job leases, recovery, deduplication and dead-letter processing under real multi-worker tests.

## Release classification

`v1.0-alpha8` remains **Production Architecture Alpha**, not Production Ready. Live external infrastructure capabilities must remain `NOT VERIFIED` until a real staging certification report proves otherwise.
