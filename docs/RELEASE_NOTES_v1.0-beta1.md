# Release Notes · CareerOS v1.0-beta1

## Business Runtime Verification Candidate

### P0 stabilization update

- fixed FastAPI route verification to use public OpenAPI behavior instead of a
  flat `app.routes` implementation detail;
- made SQLite snapshot JSONL bytes and SHA256 manifests consistent across
  Windows and Linux;
- fixed pytest 9 pass counting in the isolated test matrix;
- added a fully pinned, hash-verified `requirements.lock` and fixed CI to
  Python 3.11.9;
- added the proprietary `LICENSE` and `SECURITY.md`;
- passed 132/132 tests in
  [GitHub Actions run 29988693142](https://github.com/a2098127101-droid/CareerOS/actions/runs/29988693142).

This update does not change the pre-release status or claim Runtime Verified.

### Added

- signed Business E2E certificate and production readiness gate;
- real authenticated Agent-chain certification with live model-usage proof;
- expanded cross-tenant attack suite;
- semantic RAG quality fixture with authority/year/isolation checks;
- ephemeral certification identities with post-run de-identification;
- independent Redis worker certification;
- stale-worker lease recovery certification foundation;
- actual presigned-URL HTTP download/checksum verification;
- disposable SQLite→PostgreSQL migration certification;
- disposable PostgreSQL backup/restore certification;
- measured staging load-smoke gate;
- external observability sink health certification hook;
- beta1 staging gate and documentation.

### Changed

- Runtime certification no longer self-runs worker jobs.
- Worker/API handler registration is shared through `app/job_handlers.py`.
- Runtime certification model configuration uses the active RepositoryContainer backend.
- Production `/ready` requires both Runtime and Business certificates.
- Staging Compose project name/version updated to beta1.

### Not claimed

- no live PostgreSQL/pgvector/Redis/MinIO/Embedding/LLM certification was possible in the build environment;
- no 100/500/1000 concurrent AI capacity claim;
- observability check is a health-endpoint probe, not event-ingestion proof;
- real Billing and Enterprise SSO remain not ready.
