# Test Report — CareerOS v1.0-alpha4

## Automated regression

Three regression batches completed successfully:

- Batch A: 20 passed
- Batch B: 24 passed
- Batch C: 34 passed, 11 Python/SQLite deprecation warnings

**Total: 78 passed.**

Warnings are SQLAlchemy/SQLite datetime adapter deprecation warnings under Python 3.13 and are not test failures.

## New alpha4 coverage

- memory rate limiting;
- background jobs and tenant scoping;
- automatic transient job retry;
- upload magic/MIME/archive policies;
- signed-file token integrity;
- local private storage lifecycle;
- migration 12 / Alembic 0003;
- private file access API;
- SSE progressive response API;
- async knowledge reindex job;
- runtime metrics/probes;
- non-demo production runtime configuration guards;
- production CSRF Origin validation.

## Environment limitations

Not physically/live verified:

- PostgreSQL/pgvector server;
- Redis server;
- S3/R2/MinIO service;
- malware scanner executable;
- Safari/Firefox physical browser runs;
- live external model APIs.
