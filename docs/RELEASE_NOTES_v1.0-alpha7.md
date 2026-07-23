# Release Notes · v1.0-alpha7

CareerOS v1.0-alpha7 reduces architecture debt and makes core product behavior less dependent on fixed school/competition assumptions.

## Highlights

1. Centralized schema ownership: Store-local DDL removed.
2. Preset-aware workflow templates with different stage counts and requirements.
3. Generic artifact-template resolution with backward-compatible aliases.
4. Evidence-grounded Job Intelligence matching.
5. Persistent verification history and authorized human Claim override.
6. First route extraction from the large `main.py` composition module.
7. Migration 15 / Alembic 0006; 42-table schema manifest.
8. 101 automated tests collected and passed in release batches.

## Still not Production Ready

Live infrastructure certification remains the highest priority. PostgreSQL/pgvector, Redis, object storage, embedding, generation LLM, observability, recovery drills and real load tests must be executed in a real staging environment before promoting the project to Runtime Verified Beta.
