# Test Report · CareerOS v1.0-alpha6

## Automated regression

- Python compile: PASS
- pytest: **93 passed**
- warnings: 12 SQLite/Python datetime deprecation warnings; no test failures
- Repository contract audit: **12 / 12 pairs, missing methods = 0**

## New alpha6 coverage

- console email outbox truthfulness;
- generic invitation/password-reset templates;
- runtime certification truthful status when services are absent;
- controlled privacy deletion/de-identification;
- SQLAlchemy identity anonymization parity;
- SQLite backup/restore round-trip;
- API invitation email delivery metadata;
- privacy deletion plan / confirmation / execution API.

## Not live verified in this build environment

- PostgreSQL + pgvector;
- Redis distributed runtime;
- S3/R2/MinIO round-trip;
- semantic embedding provider;
- real LLM provider;
- SMTP server;
- Sentry/OpenTelemetry collector;
- PostgreSQL backup/restore drill;
- 100/500/1000 concurrency staging load test.
