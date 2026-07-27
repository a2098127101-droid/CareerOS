# CareerOS v1.4 Canonical Runtime — Changelog

## Release focus
v1.4 removes the remaining high-risk runtime shortcuts that could corrupt multi-user data or create a second business source of truth.

## Fixed
- Owner-scoped runtime identity: `(tenant_id, owner_user_id, entity_type, entity_id)`; identical client IDs can safely exist for different users.
- Explicit subject-user authorization. Advisors require a real shared class relationship; organization admins remain tenant scoped.
- Removed tenant-wide staff collection replacement for canonical business entities.
- Generic runtime is restricted to UI/session/cache-like state. Evidence, Artifact, Task, User, Knowledge and Job use canonical stores/APIs.
- Added entity versioning/revision metadata and optimistic locking for Evidence, Artifact and Task mutations, including Task delete.
- Removed 5,000-row runtime snapshot truncation; state paging now drains all pages and v2 supports change/revision APIs.
- Fixed Artifact version-chain defects: explicit artifact IDs create independent series, same-kind artifacts no longer merge, series version advances with V1/V2/V3.
- Added migration 18 (runtime consistency/lifecycle) and migration 19 (artifact multi-series compatibility).
- Regenerated `schema_manifest.json` and PostgreSQL baseline from migrations 1–19; SQLite/PostgreSQL repository parity restored.
- H5 API mode now uses canonical Evidence/Artifact/Task/User/Knowledge/Job endpoints rather than business JSON collection replacement.
- Knowledge upload/search uses canonical parser/RAG endpoints in API mode; Job CSV import/match uses canonical Job Intelligence endpoints.
- AI Coach, Interview evaluation and PPT review use configured ModelGateway routes in API mode. Missing model routes return `503 ai_route_unavailable`; no fabricated API-mode score/reply fallback.
- Added provider SSRF guard and plaintext-secret-key detection for custom headers/query parameters; private/self-hosted network access is explicit and disabled by default.
- CI no longer hardcodes historical test counts; it verifies that every discovered `tests/test_*.py` file was executed and no file failed.
- H5/server Showcase copies synchronized; version identifiers updated to v1.4.

## Validation
- 35 test files.
- 148/148 tests passed in three non-overlapping groups: 43 + 35 + 70.
- Python compileall passed.
- H5 JavaScript syntax passed for all inline script blocks.
- FastAPI startup smoke passed; 184 routes registered.
- `/api/health`, `/live`, `/ready`, `/api/workspace/v1/context` returned HTTP 200 in local development/demo runtime.

## Known boundaries
Production readiness still requires real PostgreSQL/Redis/worker/object-storage/model credentials, target-environment certification, full browser E2E on a supported runner, and further frontend modularization. See `REMAINING_GAPS_v1.4.md`.
