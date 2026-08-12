# StepIn 2.2 Web Deployment

## Current supported deployment shape

The current StepIn production architecture supports FastAPI behind TLS with PostgreSQL/pgvector, authenticated Redis and an independent worker, private S3-compatible object storage, and production observability. SQLite remains a local compatibility backend rather than the target multi-instance production repository.

```text
Domain / HTTPS
      ↓
Caddy / reverse proxy
      ↓
StepIn Web + FastAPI
      ↓
PostgreSQL + pgvector
Redis + independent worker
Private object storage
Observability
```

## Production requirements

At minimum configure `APP_ENV=production`, `DEMO_MODE=false`, `AUTH_REQUIRED=true`, strong externally managed secrets, secure cookies, explicit origins, reviewed model-provider routes, semantic retrieval and private object storage. The application database role must be non-owner, non-superuser and `NOBYPASSRLS`.

The current production flow must verify more than infrastructure health: Foundation, bounded Learner Agent intervention, revision, transfer, Evidence/Artifact persistence, Project Library v2.2, teacher/human review and tenant isolation should all pass in the target environment.

## Go-live boundary

Use `deploy/README_PRODUCTION.md` and `deploy/PRODUCTION_CHECKLIST.md` as the current authoritative deployment documents. Do not infer production readiness from container startup or source-code CI alone.
