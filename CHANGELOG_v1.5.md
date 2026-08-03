# CareerOS v1.5 Changelog

## Added

- Persistent Claim, Claim Version and Claim relation models.
- Capability taxonomy/definition/version and Capability Assessment history.
- Requirement Version and Requirement–Capability Mapping.
- Career Gap and Gap Version lifecycle.
- Domain audit events.
- `/api/domain/v1` API.
- Unified H5 Domain Intelligence panels and explanation actions.
- PostgreSQL repository parity and Alembic `0009`.
- v1.5-specific regression tests.
- Forward-only `0010` repair/hardening migration and immutable `0007` guard.
- Canonical `/api/v1` aliases and OpenAPI cookie authentication scheme.
- True Okapi BM25, configurable remote Reranker adapters and a Demo retrieval
  evaluation fixture.
- Forced PostgreSQL tenant RLS policies and tenant-first indexes.

## Changed

- Capability Profile in API mode is server-authoritative.
- Job Positioning distinguishes Potential Match, Verified Match and Evidence Coverage.
- Lexical overlap remains candidate support, not verified support.
- Evidence Trust fields are part of the canonical repository contract.
- Workspace AI routes are included in explicit rate-limit policies.
- System and model-administration routes are split from `main.py`.
- PostgreSQL certification uses a truly isolated schema and unique run identity.

## Fixed

- PostgreSQL Evidence Trust repository parity.
- Requirement and Gap version-history persistence.
- Alembic seed binding on SQLite/PostgreSQL-compatible migrations.
- Historical tests that pinned the previous Alembic head or insecure self-verification semantics.
- Missing `pytest-asyncio` CI dependency and DNS-dependent SSRF tests.
- Lazy-router discovery when generating `/api/v1` aliases on newer FastAPI.
- Worker image HTTP healthcheck mismatch in Docker Compose.
- Student workflow `undefined` fields with PostgreSQL-persisted metadata.
