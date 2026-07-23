# Release Notes · CareerOS v1.0-beta0

## Added

- signed `careeros-runtime-certification-v2` reports;
- deployment-environment fingerprint binding;
- configurable certification freshness window;
- live pgvector certification check;
- distributed Redis rate-limit cross-client probe;
- Redis job queue/state/worker round-trip probe;
- S3 put/get/presign/delete certification probe;
- full/infrastructure/AI certification profiles;
- production `/ready` certification gate;
- full staging Compose topology with PostgreSQL+pgvector, Redis, MinIO, API, worker and certifier;
- staging preflight and one-shot runtime gate scripts;
- CI workflow for compile/audits/isolated regression matrix;
- beta0 certification regression tests.

## Changed

- runtime certification now uses the configured RepositoryContainer model repository rather than bypassing production PostgreSQL with local SQLite model configuration;
- worker startup no longer imports the FastAPI app;
- background job handlers are shared through a worker-safe registration module;
- production readiness treats invalid/missing/stale full runtime certification as a blocker.

## Not claimed

This package is a **Runtime Certification Candidate**, not a successful live Runtime Verified build. External infrastructure remains `NOT VERIFIED` until the staging gate is run against real provisioned services and credentials.
