# Backup & Restore · v1.0-alpha6

## SQLite

Backup:

```bash
python scripts/backup_database.py --backend sqlite --sqlite-path data/agent.db --out backups/careeros.db
```

Restore:

```bash
python scripts/restore_database.py --backup backups/careeros.db --sqlite-target data/restored.db --confirm
```

Backups include a SHA256 manifest. Restore refuses a checksum mismatch.

## PostgreSQL

Backup uses `pg_dump` custom format. Restore uses `pg_restore`.

```bash
python scripts/backup_database.py --backend postgresql --database-url "$DATABASE_URL" --out backups/careeros.dump
python scripts/restore_database.py --backup backups/careeros.dump --database-url "$DATABASE_URL" --confirm
```

A real PostgreSQL backup/restore drill remains `NOT VERIFIED` until these commands are executed against staging and data integrity is checked after restore.
