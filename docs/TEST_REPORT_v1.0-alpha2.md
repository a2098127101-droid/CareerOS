# Test Report — CareerOS v1.0-alpha2

## Results

The pytest suite reached:

```text
61 passed
11 warnings
```

The warnings are Python 3.13 SQLite datetime-adapter deprecation warnings emitted by SQLAlchemy's SQLite test backend; they are not test failures.

## Added coverage

- Full SQLAlchemy repository adapter smoke/contract paths.
- Static public-method contract audit across all 12 legacy/SQLAlchemy repository pairs.
- Identity/session tenant isolation.
- Artifact/evidence/workflow/feedback/task parity.
- Model provider/route/usage repository roundtrip.
- Knowledge/job/commercial/storage-registry adapters.
- Session metadata and owner reassignment parity.
- Cross-tenant knowledge/job/evidence-graph isolation checks.
- PostgreSQL DDL compilation.
- Schema health fail-closed behavior.
- Snapshot checksum corruption detection.
- Generic Agent demo flow without forced competition track.
- PostgreSQL certification fingerprint/schema binding.
- H5 hash router synchronization and JavaScript syntax.

## Additional smoke checks

Development-mode API smoke returned HTTP 200 for:

- `/api/health`
- `/api/product/config`
- `/showcase`
- `/participant`
- `/advisor`

Inline JavaScript syntax checks passed for:

- `student.html`
- `teacher.html`
- `admin.html`
- `login.html`
- `CareerOS_H5_Showcase.html`

## Explicitly not tested

- Live PostgreSQL server CRUD/integration: **NOT VERIFIED**
- SQLite → live PostgreSQL import: **NOT VERIFIED**
- pgvector: **NOT IMPLEMENTED**
- Redis/background workers: **NOT IMPLEMENTED**
- Real external LLM API E2E: **NOT VERIFIED**
- Safari/Firefox/Windows physical browser execution: **NOT PHYSICALLY VERIFIED in this build environment**
