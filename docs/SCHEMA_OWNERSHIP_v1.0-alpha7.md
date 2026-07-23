# Schema Ownership · v1.0-alpha7

## Previous risk

Historically, schema creation existed in three places:

- Store-local `CREATE TABLE IF NOT EXISTS` blocks;
- legacy SQLite migration functions;
- PostgreSQL Alembic migrations.

This made schema drift possible.

## Alpha7 change

Store-local table/index DDL has been removed. SQLite compatibility initialization now calls the centralized migration layer, which materializes checked-in SQLAlchemy metadata before applying compatibility/data migrations.

Run:

```bash
python scripts/audit_database_access.py
```

Expected:

```text
unexpected = []
store_owned_ddl_violations = []
schema_ownership = CENTRALIZED
status = TRANSITION
```

`TRANSITION` is intentional because SQLite CRUD repository implementations still directly use `sqlite3` for local compatibility. Removing direct SQLite access entirely is not claimed in alpha7.

## PostgreSQL

PostgreSQL schema ownership remains Alembic-only. Current head:

```text
0006_template_engine_foundation
```

Live PostgreSQL migration/certification remains `NOT VERIFIED` in this build environment.
