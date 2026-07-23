# Test Report · CareerOS v1.0-alpha5

## Automated coverage

Alpha5 adds tests for:

- migration 13/14 schema
- model capability registry
- capability-aware auto recommendation
- invitation create/accept/revoke foundation
- user disable/reactivate and role change
- privacy consent
- privacy export and delete-request workflow
- PII redaction
- SQLAlchemy repository parity for new identity/model methods
- signed mock billing
- webhook signature validation
- webhook idempotency
- Alpha5 API integration flow

## Verified locally

- Python compile checks.
- SQLite migration path.
- Alembic through `0005_billing_sandbox_foundation` on a fresh SQLite target.
- Repository public contract parity 12/12.
- H5 standalone/server copy synchronization.

## Not verified in the build environment

- Live PostgreSQL/pgvector.
- Live Redis worker/runtime.
- Live S3-compatible object service.
- Live semantic embedding API.
- Live generation model E2E.
- Live Sentry/OpenTelemetry sink.
- Real payment provider.
- SMTP invitation delivery.

The final release test count should be read from the release verification output; no unavailable live integration is represented as passed.

## Final local regression result

The alpha5 source tree collected **86 automated tests**.

Regression batches:

- 20 passed
- 24 passed
- 26 passed (11 Python 3.13 / SQLite datetime deprecation warnings)
- 16 passed (1 Python 3.13 / SQLite datetime deprecation warning)

Total: **86 / 86 passed**.

Additional checks:

- `python -m compileall`: PASS
- Repository public contract audit: 12 / 12 pairs, missing methods = 0
- Alembic fresh SQLite upgrade head: `0005_billing_sandbox_foundation`
- Student/Advisor/Admin/Login/H5 inline JavaScript syntax: PASS
- `app/static/ui.js`: PASS
- Standalone H5 and `/showcase` source: byte-synchronized
- Personal identity / school / major-specific historical terms scan: CLEAN for the checked release terms

These results do not substitute for live PostgreSQL/pgvector, Redis, S3, semantic model, generation model, monitoring or real payment-provider certification.
