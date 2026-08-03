# CareerOS Production Deployment Runbook

This topology is the public-server deployment target for a controlled university pilot. It does not turn an unverified environment into a certified production release by itself.

## Architecture

```text
Internet
  └─ Caddy (automatic TLS, security headers)
       ├─ CareerOS API / web UI
       └─ private MinIO object delivery host

Internal Docker network
  ├─ FastAPI API
  ├─ independent Redis worker
  ├─ PostgreSQL + pgvector
  ├─ Redis with password authentication
  └─ MinIO private bucket
```

The API uses a non-owner, non-superuser, `NOBYPASSRLS` PostgreSQL role. Alembic migrations run through a separate owner connection before the API starts.

## Server baseline

- Ubuntu 24.04 LTS or equivalent maintained Linux distribution
- Docker Engine with Compose v2
- 4 vCPU, 8 GB RAM, 80 GB SSD minimum for a pilot
- DNS A/AAAA records for `DOMAIN` and `STORAGE_DOMAIN`
- inbound TCP 80/443 and UDP 443
- outbound HTTPS access to the configured model, embedding, SMTP and monitoring providers

Do not expose PostgreSQL, Redis or MinIO API ports publicly. The MinIO console is bound to `127.0.0.1` only.

## First deployment

```bash
cd deploy
cp .env.production.example .env.production
chmod 600 .env.production
```

Replace every placeholder. Generate independent secrets, for example:

```bash
openssl rand -hex 48
```

Then run:

```bash
bash scripts/production-up.sh
```

The launch script rejects placeholder values, validates the Compose model, builds the pinned application image, runs Alembic, starts the API/worker/proxy topology and waits for `/live`.

## Required post-start gate

A successful container start is not a Runtime Verified claim. Run:

```bash
docker compose \
  --env-file .env.production \
  -f docker-compose.production.yml \
  --profile certify run --rm certifier
```

The environment is eligible for pilot traffic only after all of the following are valid and current:

1. PostgreSQL repository certification
2. Runtime certification
3. Business E2E certification
4. semantic retrieval gate
5. independent worker execution and recovery
6. private object presigned-URL HTTP round trip
7. cross-tenant attack checks
8. measured load/smoke gate
9. `/ready` returns HTTP 200

## Backup

```bash
BACKUP_DIR=/secure/backups RETENTION_DAYS=14 \
  bash scripts/backup-postgres.sh
```

Set `BACKUP_AGE_RECIPIENT` when the `age` CLI is installed to encrypt the dump before retention. Store backups outside the application server and test restore regularly.

## Restore

```bash
CONFIRM_RESTORE=RESTORE_CAREEROS \
  bash scripts/restore-postgres.sh /secure/backups/careeros-YYYYMMDDTHHMMSSZ.dump
```

The restore script stops API/worker, restores the database, reapplies Alembic and starts the application. Re-run all certification gates before reopening traffic.

## Upgrade

```bash
git fetch --tags
git checkout <reviewed-release-tag>
bash deploy/scripts/backup-postgres.sh
bash deploy/scripts/production-up.sh
```

Never deploy directly from an unreviewed feature branch. Pin a reviewed commit or release tag and retain the previous image/tag for rollback.

## Operating checks

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
curl -fsS https://${DOMAIN}/live
curl -fsS https://${DOMAIN}/ready
```

Monitor:

- API 5xx rate and latency
- background queue depth and failed jobs
- PostgreSQL storage, locks and connection saturation
- Redis memory and persistence errors
- MinIO capacity and failed object operations
- LLM call error rate, latency, token consumption and unpriced calls
- audit events for role, model, project and evidence operations

## Security boundaries

- Do not commit `.env.production`, API keys, certification files, database dumps or real student data.
- Keep self-registration disabled unless a reviewed institution-specific onboarding flow is implemented.
- Use institution-approved privacy notices, retention rules and consent records before importing student data.
- Model-generated career advice is decision support, not a validated psychometric assessment or guaranteed employment prediction.
- Keep billing disabled until a real provider adapter, webhook verification and reconciliation process have been implemented and verified.
