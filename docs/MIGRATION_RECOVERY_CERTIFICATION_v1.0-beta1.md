# Migration & Recovery Certification · v1.0-beta1

## SQLite → PostgreSQL migration drill

`scripts/certify_sqlite_postgres_migration.py` creates a realistic temporary SQLite fixture containing representative:

- tenant/user,
- session/profile,
- Evidence,
- artifact/version,
- workflow,
- knowledge source,
- commercial plan,
- analytics event.

The drill then:

```text
SQLite fixture
→ deterministic JSONL snapshot + checksums
→ disposable PostgreSQL database
→ Alembic upgrade head
→ snapshot import
→ row-count verification
→ PostgreSQL Repository read-back
→ drop disposable database
```

The target PostgreSQL role used for this certification must have permission to create/drop a disposable database. Managed services that prohibit this should run the drill against a dedicated disposable migration-test database instead of weakening the production role.

## PostgreSQL backup/restore drill

`scripts/certify_backup_restore.py` uses a disposable PostgreSQL schema:

```text
create schema + probe row
→ pg_dump
→ drop schema
→ pg_restore
→ read marker back
→ cleanup
```

The container image includes PostgreSQL client tools for the staging harness.

## Security note

Database URLs supplied to `pg_dump`/`pg_restore` can be visible to the local process environment/process inspection depending on platform. Run the drill only in controlled staging infrastructure and use the platform secret manager/environment injection rather than checked-in credentials.

## Release-gate semantics

The staging gate requires both migration and recovery drills to return `ok=true` before final PASS.

The current build environment has no live PostgreSQL server or `psycopg`, so these live drills are **NOT VERIFIED** in the build environment.
