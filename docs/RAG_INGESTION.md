# RAG Ingestion

Hybrid retrieval combines lexical/BM25-style retrieval, a vector channel, metadata/authority ranking and effective-year filtering.

`local-hash-v1` is a zero-key fallback only. Configure a real semantic embedding provider before calling the vector channel semantic.

Recommended ingestion rules:

- store authority and effective year;
- prefer current valid high-authority sources;
- flag conflicting years instead of silently merging them;
- keep structured job data out of ordinary document RAG when possible;
- never treat case content as current-user Evidence.
