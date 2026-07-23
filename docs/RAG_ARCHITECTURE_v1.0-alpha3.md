# RAG Architecture — v1.0-alpha3

## Retrieval pipeline

```text
User Query
   │
   ├─ Lexical / BM25 channel
   │
   └─ Embedding Gateway
          ├─ remote semantic provider when configured and successful
          └─ local_hash fallback when unavailable
                 │
                 ▼
          Vector retrieval
          ├─ PostgreSQL pgvector exact cosine search when certified
          └─ portable vector_json scan otherwise
                 │
                 ▼
          Hybrid fusion
                 │
          Metadata / scope / authority / year filtering
                 │
                 ▼
              Rerank
                 │
                 ▼
             Top Evidence
```

## Embedding truthfulness contract

`local_hash` is deterministic offline feature hashing. It is useful for fallback and deterministic testing, but it is **not semantic embedding**.

A query is marked semantic only when a configured remote semantic provider successfully returns embeddings. If the remote provider fails, the gateway:

1. falls back to local_hash when permitted;
2. records provider=`local_hash`;
3. records a warning;
4. does not claim semantic retrieval.

## Supported provider modes

- local_hash
- openai_compatible
- bge_compatible
- jina_compatible
- private_api

Remote modes currently expect an OpenAI-compatible embeddings response contract. Provider-specific adapters may be added without changing retrieval services.

## PostgreSQL / pgvector

Alembic revision `0002_semantic_rag_pgvector` enables the `vector` extension and adds `knowledge_embeddings.embedding_vector vector` on PostgreSQL.

Alpha3 uses exact cosine-distance search through:

```sql
embedding_vector <=> CAST(:query_vector AS vector)
```

No ANN/HNSW index is claimed. A production ANN index requires a stable, fixed dimension and benchmark evidence before choosing index parameters.

## Incremental metadata

Embeddings record:

- model
- provider
- dimensions
- version
- content_hash
- warning
- created_at

`content_hash` is the basis for future incremental reindex jobs so unchanged chunks can be skipped.

## RAG evaluation

Evaluation cases include:

- query
- expected_source_id
- expected_year
- expected_authority
- scope

Metrics:

- Recall@5
- Recall@10
- citation/source retrieval accuracy
- authority accuracy
- temporal accuracy

The current citation metric verifies retrieval of the expected source, not factual correctness of generated prose.

## Production gate

Before enabling semantic RAG in production:

- run Alembic through revision 0002;
- certify PostgreSQL/pgvector;
- run at least one real embedding provider E2E;
- build an organization-specific evaluation set;
- verify temporal and authority conflict behavior;
- benchmark exact search before deciding whether ANN indexing is needed.
