# Release Notes · v1.0-alpha8

CareerOS alpha8 moves configurable engines from built-in-only definitions toward tenant-owned, versioned configuration while adding stricter evidence and background-job governance.

## Added

- tenant workflow template registry;
- tenant artifact template registry;
- draft/version/activation semantics;
- custom template admin APIs;
- high-risk claim policy;
- human-review-required persistence;
- background-job idempotency;
- Redis lease/dead-letter foundations;
- template router module;
- migration 16 / Alembic 0007.

## Preserved

- offline standalone Showcase;
- SQLite local compatibility;
- PostgreSQL repository code path;
- multi-tenant RBAC;
- Agent runtime / model gateway;
- Hybrid RAG / Evidence Graph;
- Job Intelligence;
- privacy / identity / commercial foundations;
- legacy API compatibility.

## Still NOT VERIFIED

Live PostgreSQL/pgvector, Redis multi-instance runtime, object storage, semantic embedding, generation LLM, live observability and production capacity remain environment-dependent certification work.
