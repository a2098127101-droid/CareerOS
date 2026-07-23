# SQLite → PostgreSQL Migration — v1.0-alpha2

## Principle

Migration is explicit and verifiable. CareerOS does not silently switch some repositories to PostgreSQL while leaving others on SQLite.

## Steps

### 1. Back up SQLite

Preserve the source database before migration.

### 2. Export deterministic snapshot

```bash
python scripts/export_sqlite_snapshot.py \
  --db data/agent.db \
  --out migration_snapshot
```

Each JSONL table file has a SHA256 recorded in `manifest.json`.

### 3. Provision PostgreSQL schema

```bash
ALEMBIC_DATABASE_URL="$DATABASE_URL" alembic -c alembic.ini upgrade head
```

### 4. Dry-run import planning

```bash
python scripts/import_snapshot_to_postgres.py \
  --snapshot migration_snapshot \
  --dry-run
```

### 5. Import

```bash
python scripts/import_snapshot_to_postgres.py \
  --snapshot migration_snapshot \
  --database-url "$DATABASE_URL"
```

Before writing, the importer verifies snapshot SHA256 values. After explicit integer-ID import, known PostgreSQL sequences are repaired.

### 6. Verify row counts

```bash
python scripts/verify_migration.py \
  --snapshot migration_snapshot \
  --database-url "$DATABASE_URL"
```

### 7. Certify repository behavior

```bash
python scripts/certify_postgres.py \
  --database-url "$DATABASE_URL"
```

### 8. Cutover only after verification

Set:

```env
REPOSITORY_BACKEND=postgresql
DATABASE_URL=postgresql://...
POSTGRES_CERTIFICATION_FILE=data/postgres_certification.json
```

## Rollback strategy

Before public cutover:

- retain the original SQLite backup;
- retain the deterministic snapshot;
- take a PostgreSQL backup after import;
- do not allow dual-write mixed-runtime behavior.

A failed migration should stop before production traffic is enabled.
