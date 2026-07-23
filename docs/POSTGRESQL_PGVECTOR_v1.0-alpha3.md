# PostgreSQL + pgvector Status — v1.0-alpha3

## Implemented

- SQLAlchemy repository surface from alpha2 retained.
- Alembic revision `0002_semantic_rag_pgvector` added.
- PostgreSQL vector extension enablement path added.
- `knowledge_embeddings.embedding_vector vector` migration added.
- pgvector capability inspection added.
- exact cosine-distance search code path added.
- PostgreSQL certification harness now checks pgvector readiness.
- PostgreSQL baseline DDL regenerated from alpha3 schema manifest.

## Not verified in build environment

The build environment did not provide:

- a live PostgreSQL server;
- `psycopg` runtime connection;
- a live pgvector query target.

Therefore the following remain:

```text
Live PostgreSQL integration       NOT VERIFIED
Live pgvector retrieval           NOT VERIFIED
SQLite → live PostgreSQL import   NOT VERIFIED
```

## No ANN claim

Alpha3 does not create or claim a production HNSW/IVFFlat index. The vector column is dimension-flexible at migration time. A production vector index should be created only after:

1. choosing the embedding model and fixed dimensions;
2. measuring corpus size;
3. benchmarking exact search latency/quality;
4. selecting index parameters based on measured recall/latency.

## Staging certification sequence

```text
1. Provision PostgreSQL with vector extension support
2. Install production Python dependencies
3. alembic upgrade head
4. Import SQLite snapshot if migrating existing data
5. verify_migration.py
6. certify_postgres.py
7. configure a real semantic embedding provider
8. reindex knowledge
9. run RAG evaluation cases
10. only then consider production cutover
```
