# PostgreSQL status

## Implemented

- SQLAlchemy 2.x database engine abstraction.
- PostgreSQL URL normalization.
- Driver readiness detection.
- PostgreSQL-compilable schema metadata for the current persistent model.
- Alembic fresh-database baseline.
- Generated reference DDL at `deploy/postgresql_baseline.sql`.
- First SQLAlchemy session repository parity adapter.
- Snapshot export/import/verification tooling.

## NOT READY

The full application runtime is **not yet** PostgreSQL-ready because the following legacy adapters still directly use SQLite:

- identity/auth
- artifact
- evidence/evidence graph
- workflow
- collaboration/tasks
- knowledge/RAG
- jobs
- model configuration/usage
- commercial/analytics
- object registry

`REPOSITORY_BACKEND=postgresql` therefore fails closed rather than silently mixing PostgreSQL and SQLite.

## Current recommended modes

Local development:

```env
REPOSITORY_BACKEND=sqlite
APP_DB_PATH=data/agent.db
```

Future production target:

```env
APP_ENV=production
DEMO_MODE=false
REPOSITORY_BACKEND=postgresql
DATABASE_URL=postgresql://...
```

Do not enable the future production target until the repository parity matrix is complete.
