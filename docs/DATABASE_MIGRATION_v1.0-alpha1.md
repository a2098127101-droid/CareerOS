# SQLite → PostgreSQL migration plan

## Current strategy

Migration is staged to avoid breaking the existing Windows/local runtime.

1. Freeze and back up the v0.9 SQLite database.
2. Export deterministic JSONL snapshots.
3. Provision the v1 baseline schema with Alembic.
4. Run import in `--dry-run` mode.
5. Import into PostgreSQL only after all required repository adapters reach parity.
6. Compare row counts and tenant ownership with `verify_migration.py`.
7. Run tenant-isolation and IDOR integration tests before cutover.

## Export

```bash
python scripts/export_sqlite_snapshot.py --db data/agent.db --out migration_snapshot
```

## Provision a fresh database

```bash
set ALEMBIC_DATABASE_URL=postgresql://user:password@host:5432/careeros
alembic -c alembic.ini upgrade head
```

Install production dependencies first:

```bash
pip install -r requirements-production.txt
```

## Validate import plan without writing

```bash
python scripts/import_snapshot_to_postgres.py --snapshot migration_snapshot --dry-run
```

## Import after repository parity is complete

```bash
python scripts/import_snapshot_to_postgres.py \
  --snapshot migration_snapshot \
  --database-url postgresql://user:password@host:5432/careeros
```

## Verify counts

```bash
python scripts/verify_migration.py \
  --snapshot migration_snapshot \
  --database-url postgresql://user:password@host:5432/careeros
```

## Rollback rule

Do not delete the source SQLite database during the first production cutover. Keep an immutable backup until PostgreSQL data integrity, tenant isolation, artifacts, evidence, workflow and authentication have all been verified.
