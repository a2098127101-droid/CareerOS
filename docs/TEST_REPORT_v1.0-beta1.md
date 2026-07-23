# Test Report · CareerOS v1.0-beta1

## GitHub Actions P0 stabilization verification

Verified on 2026-07-23 in
[CareerOS CI run 29988693142](https://github.com/a2098127101-droid/CareerOS/actions/runs/29988693142):

- commit: `bff734b82a23314dd719a6a9c287ace869d7ee50`;
- runner: GitHub-hosted Ubuntu;
- Python: `3.11.9`;
- dependency installation: `pip install --require-hashes -r requirements.lock`;
- dependency integrity: `pip check` passed;
- test isolation: 32 test files, one subprocess per file;
- result: **132/132 passed**, 0 failed files;
- Python compileall: passed;
- Repository Contract: 12/12 pairs, 0 missing methods;
- Database Access Audit: 0 unexpected SQLite modules and 0 Store-owned DDL violations.

The workflow explicitly asserts `passed_tests == 132`; a pytest output-format
change cannot silently record a passing file as zero tests.

P0 stabilization also verifies:

- FastAPI modular routes through public OpenAPI paths and unique operation IDs,
  without assuming `app.routes` is a flat internal list;
- deterministic LF-only JSONL snapshot bytes and manifest SHA256 equality on
  Windows;
- pytest 9 pass counting through a pytest reporting hook.

## Packaged local build regression

The release candidate was tested in isolated pytest groups to avoid the known process-exit interaction of local background executors.

Results:

- Core / legacy / API / showcase group: **24 passed**
- Phase4 → alpha4 / Repository / RAG group: **54 passed**, 11 warnings
- alpha5 → alpha8 group: **32 passed**, 1 warning
- beta0 + beta1 group: **22 passed**

Total:

```text
132 passed
12 warnings
```

Warnings are Python 3.13 SQLite datetime-adapter deprecation warnings, not assertion failures.

## beta1-specific coverage

- independent-worker certification does not self-execute `work_once()`;
- Redis completion records worker identity;
- stale running job recovery foundation;
- actual presigned-URL HTTP GET and checksum verification;
- signed/environment-bound/fresh Business certificate;
- Business certificate tamper rejection;
- migration fixture exports representative core rows;
- staging gate includes business/migration/recovery/load gates;
- production readiness requires Business E2E certificate;
- API/worker share `runtime_probe` handler;
- certification identities use ephemeral credentials and are de-identified;
- cross-tenant business attack suite covers core session resources and tenant-scoped Job Intelligence;
- Business E2E includes Job Intelligence and Evidence Verification;
- stale-job recovery uses a per-job Redis recovery lock (`NX`) to reduce duplicate recovery races;
- internal MinIO transport can verify a browser-facing presigned host while preserving the signed Host header;
- staging preflight rejects a private MinIO hostname without a browser-facing public signing endpoint.

## Static/architecture gates

- Python compileall: PASS
- Repository Contract: 12/12, 0 missing methods
- Database Access Audit: 0 unexpected SQLite modules, 0 Store-owned DDL violations
- Alembic head: `0007_tenant_templates_evidence_risk` on fresh SQLite migration test
- Standalone H5 and server showcase: byte-identical
- JavaScript syntax: checked for student/teacher/admin/login/showcase/ui
- release package sanitization: no `.env`, runtime DB, certification reports, email outbox, cache or compiled bytecode intended for release

## Live verification status

The successful GitHub Actions regression is a code-level SQLite verification.
It does not provide a live PostgreSQL/pgvector, Redis, MinIO/S3, semantic
embedding provider, generation model, or complete staging topology.

Therefore the following are **NOT VERIFIED in this build environment**:

- live PostgreSQL/pgvector,
- independent live Redis worker topology,
- live MinIO/S3,
- live semantic RAG,
- live Agent E2E,
- live observability sink,
- PostgreSQL migration/recovery drills,
- real load/capacity certification.

The staging harness is designed to produce those results in a target environment; this document does not claim them prematurely.
