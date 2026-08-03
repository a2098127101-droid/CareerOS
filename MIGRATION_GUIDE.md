# CareerOS v1.4/v1.4.1 → v1.5 Migration

## SQLite

Startup applies migrations through version 21. Back up the database before first startup.

```bash
cp data/careeros.db data/careeros.pre-v15.db
uvicorn app.main:app
```

Verify:

```python
from app.migrations import migration_status
print(migration_status("data/careeros.db"))
```

Expected current/latest: `21`.

## PostgreSQL

```bash
alembic -c alembic.ini upgrade head
```

Expected Alembic head:

```text
0009_domain_intelligence_v15
```

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
