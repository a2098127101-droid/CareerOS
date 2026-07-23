# Web Deployment

## Current supported deployment shape

v1.0-alpha1 can run as a single FastAPI instance for controlled evaluation using Docker or a Python environment.

Do not scale it horizontally yet: the active repositories use SQLite and the rate-limit/circuit state is process-local.

## Target production stack

```text
Domain / HTTPS
      ↓
Reverse proxy / CDN
      ↓
Frontend + FastAPI
      ↓
PostgreSQL + pgvector
Redis / background worker
Private object storage
Observability
```

## Production environment requirements

At minimum configure:

- `APP_ENV=production`
- `DEMO_MODE=false`
- `AUTH_REQUIRED=true`
- strong `APP_SECRET_KEY`
- `COOKIE_SECURE=true`
- explicit `ALLOWED_ORIGINS`
- real LLM provider routes
- semantic embedding provider
- private object storage

The readiness endpoint will continue to report SQLite as a blocker until the repository migration is implemented.
