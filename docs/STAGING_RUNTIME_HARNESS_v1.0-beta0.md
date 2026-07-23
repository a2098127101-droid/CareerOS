# Staging Runtime Harness · v1.0-beta0

## Files

- `deploy/.env.staging.example`
- `deploy/docker-compose.staging.yml`
- `scripts/staging_preflight.py`
- `scripts/staging_runtime_gate.py`

## Flow

```text
Preflight
  ↓
PostgreSQL + pgvector
Redis
MinIO
  ↓
Alembic upgrade head
  ↓
Non-destructive PostgreSQL Repository Certification
  ↓
API + independent Worker
  ↓
Full Runtime Certification
  ↓
Signed certificate written
  ↓
/live + /ready
  ↓
Staging Gate PASS / FAIL
```

## Run

```bash
cd deploy
cp .env.staging.example .env.staging
# replace every CHANGE_ME value

docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build postgres redis minio minio-init api worker

docker compose --env-file .env.staging -f docker-compose.staging.yml --profile certify run --rm certifier
```

The final command must exit non-zero when any required live dependency is not verified.

## Current build-environment limitation

Docker is not available in the environment used to assemble this package, so Compose services were syntax-inspected but not physically started here. Do not treat the included harness as a successful live certification report.
