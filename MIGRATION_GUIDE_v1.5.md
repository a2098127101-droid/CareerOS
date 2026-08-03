# CareerOS v1.4/v1.4.1 → v1.5 Migration

## SQLite

Startup applies migrations through version 22. Back up the database before first startup.

```bash
cp data/careeros.db data/careeros.pre-v15.db
uvicorn app.main:app
```

Verify:

```python
from app.migrations import migration_status
print(migration_status("data/careeros.db"))
```

Expected current/latest: `22`.

## PostgreSQL

```bash
alembic -c alembic.ini upgrade head
```

Expected Alembic head:

```text
0012_project_tenant_rls
```

`0010` is forward-only. It restores the published `0007` migration to its
original immutable content, creates missing Unified Runtime tables for
deployments that had already applied that release, adds tenant-first indexes,
and enables/forces PostgreSQL tenant RLS policies. Do not rewrite or re-run
`0007`.

`0011` adds the Project MVP foundation and `0012` adds the project tenant RLS
policies. Both are part of the current linear head and must be applied after
`0010`.

Production PostgreSQL must use a dedicated non-owner, non-superuser,
`NOBYPASSRLS` application role. The migration/owner role is for schema changes,
not normal application traffic.

## Created domain tables

- capability taxonomies, definitions and versions;
- claims and claim versions;
- Claim–Evidence and Claim–Capability links;
- requirement versions and Requirement–Capability links;
- capability assessments and contribution rows;
- gaps and gap versions;
- domain audit events.

## Backward compatibility

Existing Evidence with `verified=1` is migrated to `VERIFIED`; all other records become `SELF_REPORTED`. Review this migration decision before production if historical `verified` values were not created by an authorized process.
