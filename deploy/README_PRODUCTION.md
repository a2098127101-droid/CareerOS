# StepIn 2.2 Production Deployment Runbook

This runbook describes the current target topology for a controlled StepIn pilot. Source-code CI and a successful container start do not by themselves certify a production environment.

## Target topology

```text
Internet
  └─ Caddy / TLS
       ├─ StepIn API + web UI
       └─ private object-delivery host

Internal network
  ├─ FastAPI application
  ├─ independent Redis worker
  ├─ PostgreSQL + pgvector
  ├─ authenticated Redis
  └─ private MinIO / S3-compatible storage
```

The application database connection must use a non-owner, non-superuser, `NOBYPASSRLS` role. Alembic migrations run through a separate owner connection before the application starts.

## First deployment

```bash
cd deploy
cp .env.production.example .env.production
chmod 600 .env.production
bash scripts/production-up.sh
```

Replace every placeholder before launch. Do not expose PostgreSQL, Redis or MinIO API ports publicly.

## Required post-start certification

```bash
docker compose \
  --env-file .env.production \
  -f docker-compose.production.yml \
  --profile certify run --rm certifier
```

Pilot traffic should open only after the current production checklist is evidenced and `/ready` returns HTTP 200. At minimum verify PostgreSQL/RLS isolation, Redis worker execution and recovery, private object delivery, semantic retrieval, configured generation routes, student and teacher business E2E, cross-tenant negative access, load smoke, backup/restore and monitoring.

## StepIn business-flow smoke

A target-environment smoke test must include the current StepIn path rather than only historical project APIs: beginner enters Foundation, performs a real task, requests bounded Agent support when needed, produces and revises work, completes a transfer task, generates process Evidence, enters a current Project Library v2.2 project, receives teacher/human review where required, and retains a verifiable trajectory without bypassing gates.

## Backup and restore

Use the existing production backup/restore scripts and store encrypted backups off-server. Some restore environment variables and historical data-path identifiers retain `CAREEROS` names for compatibility; they are implementation identifiers, not current product branding. Re-run all certification gates after restore or upgrade before reopening traffic.

## Upgrade

```bash
git fetch --tags
git checkout <reviewed-stepin-release-tag>
bash deploy/scripts/backup-postgres.sh
bash deploy/scripts/production-up.sh
```

Never deploy directly from an unreviewed feature branch. Retain the previous reviewed image/tag for rollback.

## Operating checks

```bash
docker compose --env-file .env.production -f docker-compose.production.yml ps
curl -fsS https://${DOMAIN}/live
curl -fsS https://${DOMAIN}/ready
```

Monitor API error rate and latency, queue depth and failed jobs, PostgreSQL saturation, Redis persistence, object-storage capacity, model call failures/latency/tokens/unpriced calls, and audit events for role, learner, project, Evidence and policy-calibration operations.

## Current boundaries

- Do not commit runtime secrets, real learner data, certification files or database dumps.
- Use institution-approved privacy notices, consent/authorization, retention rules and support ownership before importing real learner data.
- Learner Trajectory and Policy Calibration require tenant isolation and human-governed activation.
- Engineering tests do not establish pedagogical effectiveness.
- Windows x64 installation, offline operation, upgrade and backup/restore remain a separate release gate until certified on real Windows hardware.
