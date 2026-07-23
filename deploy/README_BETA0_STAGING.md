# CareerOS v1.0-beta0 Staging Runtime Certification

This harness is designed to turn implemented integrations into evidence-backed runtime checks. It does not mark a dependency PASS because configuration exists.

## 1. Prepare environment

```bash
cd deploy
cp .env.staging.example .env.staging
```

Replace every `CHANGE_ME` value. For a **full** certification also configure a real semantic embedding provider and at least one real LLM provider/API key.

## 2. Start staging stack

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build postgres redis minio minio-init api worker
```

The API container performs `alembic upgrade head` and a non-destructive PostgreSQL repository/pgvector certification before starting Uvicorn.

## 3. Run full certification gate

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml --profile certify run --rm certifier
```

The gate verifies:

- live PostgreSQL repository certification;
- pgvector extension/vector column;
- Redis connectivity;
- distributed Redis rate-limit state across two independent clients;
- Redis queue/state/worker round-trip;
- private S3/MinIO put/get/presign/delete round-trip;
- remote semantic embedding call with no local-hash fallback;
- live LLM provider connectivity;
- signed, environment-bound, freshness-limited runtime certificate;
- `/live` and `/ready` after certification.

A missing or stale signed full certificate keeps production readiness closed.

## 4. Important boundary

This repository cannot claim these checks PASS until the command is run against actual provisioned services. The packaged release contains the harness, not fabricated certification results.
