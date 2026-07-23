# Release Notes — v1.0-alpha3 Semantic RAG

## Highlights

- Added semantic embedding provider runtime path with batching, retry/backoff and explicit local fallback.
- Added PostgreSQL pgvector migration and exact cosine-search code path.
- Added RAG evaluation dataset/runtime and admin API.
- Added claim verification states and persistent Evidence Verification results.
- Added numeric/negation/semantic-assisted verification foundation.
- Strengthened PostgreSQL certification to require pgvector readiness.
- Upgraded schema manifest to 33 tables while preserving staged legacy schema ownership.
- Updated generic Showcase to expose semantic RAG/Evidence Verification concepts without personal data.

## Compatibility

Preserved:

- SQLite local runtime.
- Existing APIs.
- Repository parity foundation.
- Auth/RBAC/Tenant.
- Multi-Model Gateway.
- Workflow/Artifact/Evidence traceability.
- Windows launcher.
- Standalone H5 Showcase.

## Important boundaries

Not production-certified in this environment:

- live PostgreSQL;
- live pgvector;
- real semantic embedding API;
- real LLM E2E;
- Redis/background jobs;
- private signed file delivery;
- real billing.

`local_hash` remains a deterministic fallback and must not be described as semantic embedding.
