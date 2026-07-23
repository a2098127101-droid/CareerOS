# Test Report · CareerOS v1.0-alpha8

## Release regression

The suite is executed in isolated groups because earlier versions contain process-local background executors that can keep a monolithic pytest process alive after all assertions complete.

Validated total: **110 tests passed**.

Group results:

- Group A: 22 passed
- Group B: 23 passed
- Group C: 26 passed, 11 SQLite datetime deprecation warnings
- Group D: 39 passed, 1 SQLite datetime deprecation warning

Warnings are Python 3.13 / sqlite3 datetime adapter deprecations and are not functional failures.

## Additional alpha8 coverage

- tenant custom workflow activation changes new runtime workflow shape;
- tenant template isolation;
- custom artifact resolution;
- background-job idempotency;
- high-risk evidence human-review signaling;
- persisted risk metadata in claim/history;
- template administration API and runtime integration;
- migration 16;
- Alembic head `0007_tenant_templates_evidence_risk`;
- repository contract 12/12;
- centralized schema ownership audit.

## Verified build-time facts

- Python compile: PASS
- Repository contract: 12 pairs, 0 missing public methods
- Database access audit: 0 unexpected SQLite modules, 0 Store-owned DDL violations
- Alembic fresh SQLite upgrade: PASS to `0007_tenant_templates_evidence_risk`
- Schema manifest: `1.0-alpha8`, 44 business tables
- Standalone H5 and server showcase: synchronized

## Not live verified

No alpha8 test claims live certification for PostgreSQL, pgvector, Redis distributed failover, S3/R2/MinIO, external embedding, external generation LLM, SMTP delivery, observability exporters, real payment, SSO, PostgreSQL disaster recovery or 100/500/1000-concurrency production capacity.
