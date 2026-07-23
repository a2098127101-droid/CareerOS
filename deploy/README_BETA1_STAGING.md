# CareerOS v1.0-beta1 · Staging Business Runtime Verification

## Goal

Produce verifiable evidence that both infrastructure and the CareerOS business path work in a production-like staging topology.

## Topology

```text
PostgreSQL + pgvector
Redis
MinIO/S3-compatible private storage
API
Independent Worker
Certifier
Real semantic Embedding provider
At least one real generation LLM provider
External observability/collector health endpoint
```

## 1. Configure

```bash
cd deploy
cp .env.staging.example .env.staging
```

Replace every `CHANGE_ME` value. For full certification also configure:

- a real semantic embedding provider,
- the browser-facing `S3_PUBLIC_ENDPOINT` (the example uses `127.0.0.1:9000`) and internal `S3_CERTIFICATION_FETCH_ENDPOINT` for MinIO certification,
- at least one real generation Provider/model,
- `OBSERVABILITY_CERTIFICATION_URL`.

Never commit `.env.staging`.

## 2. Start runtime

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml up -d --build postgres redis minio minio-init api worker
```

The API container runs:

- staging preflight,
- Alembic upgrade,
- PostgreSQL Repository certification,
- FastAPI startup.

## 3. Run the full gate

```bash
docker compose --env-file .env.staging -f docker-compose.staging.yml --profile certify run --rm certifier
```

The certifier requires PASS for:

1. signed Runtime Certification;
2. signed Business E2E Certification;
3. SQLite→PostgreSQL migration drill;
4. PostgreSQL backup/restore drill;
5. measured load-smoke gate;
6. `/live` and `/ready`.

The report is written to:

```text
/app/data/staging_gate_report.json
```

A valid release candidate exits with code `0`. Any required failure exits non-zero.

## Important limitations

- The migration certification creates a temporary PostgreSQL database and therefore requires staging privileges to create/drop databases. On managed platforms, use a dedicated disposable migration-test database if the application role lacks those privileges.
- The default load gate is intentionally small (100 requests / concurrency 20). It is not a 100/500/1000 concurrent AI capacity benchmark.
- The observability gate currently checks an external health endpoint; it does not yet prove event/span ingestion.
- Do not run destructive certification against a production database. Use staging/disposable resources.
