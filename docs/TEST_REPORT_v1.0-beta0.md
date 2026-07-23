# Test Report · CareerOS v1.0-beta0

## Automated regression

Total collected tests: **118**.

Executed in isolated groups to avoid lifecycle/thread teardown interference from local background executors:

- Group A: 22 passed
- Group B: 31 passed, 11 Python/SQLite deprecation warnings
- Group C: 25 passed, 1 Python/SQLite deprecation warning
- Group D + beta0: 40 passed

Total: **118 passed**.

## beta0-specific coverage

- signed runtime certificate validation;
- environment binding;
- credential rotation does not alter endpoint fingerprint;
- certificate tamper rejection;
- certificate freshness/expiry rejection;
- incomplete certification rejection;
- staging placeholder-secret preflight rejection;
- worker does not import FastAPI `app.main`;
- API and worker share the same registered background handlers;
- staging Compose declares PostgreSQL/pgvector, Redis, MinIO, API, worker and certifier.

## Other verification

- Repository contract: 12/12 pairs, 0 missing public methods.
- Database access audit: 0 unexpected SQLite modules; 0 store-owned DDL violations; schema ownership remains centralized, with 12 legacy local SQLite CRUD modules retained.
- Fresh Alembic upgrade: head `0007_tenant_templates_evidence_risk` on SQLite compatibility database.
- JavaScript syntax: student, advisor/teacher, admin, login, showcase and shared UI scripts pass syntax checks.
- Standalone H5 and server showcase are synchronized.

## Not physically verified in this build environment

- Docker Compose service startup;
- live PostgreSQL/pgvector;
- live Redis multi-instance/failover;
- live MinIO/S3/R2;
- real semantic embedding API;
- real generation LLM E2E;
- live SMTP/observability exporters;
- PostgreSQL disaster-recovery drill;
- 100/500/1000-concurrency production capacity.
