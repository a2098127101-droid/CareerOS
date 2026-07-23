# Test Report · CareerOS v1.0-alpha7

## Automated regression

Final source tree collection:

```text
101 tests collected
```

Executed in four clean batches to avoid a known interpreter-exit delay from long-lived background executor threads:

```text
Batch 1: 23 passed
Batch 2: 31 passed, 11 warnings
Batch 3: 24 passed
Batch 4: 23 passed, 1 warning
Total:   101 passed
```

Warnings are Python 3.13 / SQLite datetime-adapter deprecation warnings and are not functional test failures.

## Alpha7-specific coverage

- Store modules no longer own table DDL.
- Presets create different workflow shapes and persist template IDs.
- Legacy and enterprise artifact aliases resolve to canonical templates.
- Job Intelligence does not infer a participant skill from a job requirement.
- Evidence verification history preserves AI→human decisions.
- Migration 15 is current in the legacy SQLite migration track.
- Workflow/artifact template APIs and Job Match API work end-to-end in local mode.
- Privacy and commercial routes are modularized without duplicate FastAPI registrations.

## Schema/migration checks

- `python -m compileall`: PASS.
- PostgreSQL DDL generation from schema manifest: PASS.
- Schema manifest: `1.0-alpha7`, 42 business tables.
- Fresh SQLite Alembic upgrade: PASS.
- Alembic head: `0006_template_engine_foundation`.
- Fresh schema includes `workflow_instances.template_id`, `job_requirements`, `evidence_verification_history`.
- Repository public-contract audit: PASS, no missing methods.
- Database access audit: no unexpected SQLite modules and no Store-owned DDL violations.

## Browser/static checks

- Standalone H5 and server `/showcase` source are byte-synchronized.
- JavaScript syntax checks pass for Student, Advisor/Teacher, Admin, Login, shared UI and Showcase scripts.

## Not verified

No test report in alpha7 claims live certification for PostgreSQL, pgvector, Redis, S3/R2/MinIO, external semantic embedding, generation LLM, SMTP, observability exporters, real payment, SSO, PostgreSQL disaster recovery, or 100/500/1000 concurrent production capacity.
