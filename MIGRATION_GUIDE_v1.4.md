# CareerOS v1.3 → v1.4 Migration Guide

1. Back up the v1.3 database and browser cache.
2. Deploy v1.4 code.
3. Development SQLite: run normal startup/migrations through migration 19.
4. PostgreSQL: apply Alembic through `0008_canonical_runtime_consistency` using the deployment migration account before starting application workers.
5. Verify `/api/health` reports version `1.4.0-beta-canonical-runtime` and expected repository backend.
6. Reconfigure staff workflows to use explicit subject users; advisors need shared class relationships.
7. Do not use legacy generic runtime collection APIs for Evidence/Artifact/Task/User/Knowledge/Job; they now fail closed.
8. For local Showcase data, migrate only supported Evidence/Artifact/Task drafts. Re-import knowledge files and job CSVs through canonical flows; invite/create real users through identity APIs.
9. Configure model routes for `coach` and `reviewer` before enabling API-mode AI features.
10. Run repository tests and target-environment runtime/business certification before production cutover.
