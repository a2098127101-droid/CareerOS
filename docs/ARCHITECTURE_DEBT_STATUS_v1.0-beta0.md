# Architecture Debt Status · v1.0-beta0

## Reduced in beta0

### Worker/web coupling

Resolved for background-worker startup. `scripts/run_worker.py` no longer imports `app.main`; shared handlers live in `app/job_handlers.py`.

### Runtime-certification trust

Raw unsigned JSON is no longer sufficient for production readiness. Certificates are signed, environment-bound and freshness-limited.

### Certification/runtime repository mismatch

`certify_runtime.py` now resolves model configuration through the same `RepositoryContainer` backend selected by the runtime. A PostgreSQL certification no longer silently reads model routes from local SQLite.

## Still open

- `app/main.py` remains large (~2.1k lines) and should continue router/service decomposition.
- 12 legacy direct-SQLite CRUD modules remain intentionally for local compatibility.
- PostgreSQL live migration/certification is not verified in this build environment.
- Workflow/Artifact engines have persistent tenant templates but no full visual rule builder.
- Evidence verification still needs full NLI/entailment calibration.
- Real billing and enterprise SSO remain not ready.
