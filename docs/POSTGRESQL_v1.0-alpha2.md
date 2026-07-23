# PostgreSQL Status — v1.0-alpha2

## Implemented

- SQLAlchemy 2.x repository adapters for the current persistence surface.
- PostgreSQL-compilable schema metadata.
- Alembic baseline.
- Schema-health fail-closed guard.
- SQLite snapshot export/import/verification tooling.
- Snapshot SHA256 validation.
- Integer sequence repair after explicit-ID import.
- Non-destructive live PostgreSQL repository certification harness.

## Live certification workflow

1. Provision PostgreSQL.
2. Install `requirements-production.txt`.
3. Run `alembic upgrade head` against the target.
4. Migrate/verify data if applicable.
5. Run:

```bash
python scripts/certify_postgres.py \
  --database-url "$DATABASE_URL" \
  --out data/postgres_certification.json
```

The script:

- checks the actual target schema;
- creates a disposable `careeros_cert_*` schema;
- exercises identity/session/artifact/evidence/workflow/feedback/task/knowledge/job/commercial/storage-registry repository paths;
- drops the disposable schema;
- writes a certification only on success.

## Current build-environment boundary

This execution environment did not provide a PostgreSQL driver or server, so live certification was not executed here.

Status:

- Repository adapter code parity: **COMPLETE**
- PostgreSQL dialect DDL compile: **VERIFIED**
- Live PostgreSQL server integration: **NOT VERIFIED HERE**
- Production cutover: **NOT READY until target certification succeeds**
