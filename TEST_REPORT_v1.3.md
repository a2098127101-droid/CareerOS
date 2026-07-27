# CareerOS v1.3 Test Report

Version: `1.3.0-beta-unified-runtime`

Date: 2026-07-23

## Repository regression

34 test files were executed in three non-overlapping groups because a single long-running invocation is less reliable in the current execution environment.

| Group | Result |
| --- | --- |
| Group 1: API phase 3/4, evidence, knowledge, model store, auth/tenant, workflow, rules, showcase, v0.6/v0.9 | 37 passed |
| Group 2: alpha2–alpha5 repository/runtime/semantic/API suites | 34 passed |
| Group 3: alpha5–beta1, data foundation, certification, v1.2 and v1.3 suites | 70 passed |
| **Total** | **141 passed / 141** |

Warnings: SQLAlchemy/SQLite emitted the existing Python 3.13 datetime adapter deprecation warning in repository parity tests. No functional failures remained.

## v1.3-specific automated coverage

`tests/test_v13_unified_runtime.py` verifies:

1. owner-scoped collection replacement;
2. runtime API state CRUD and snapshot;
3. authenticated same-tenant owner isolation;
4. cross-tenant isolation;
5. student write denial for tenant-shared user directory;
6. H5 Service/DataAdapter/FastAPI architecture markers.

Result:

```text
4 passed
```

## Migration regression

The first v1.3 implementation added a new Alembic 0008 revision. Existing tests exposed a fresh-install conflict because the v1 baseline is generated from the current schema manifest. This was corrected.

Final behavior:

- Alembic compatibility head remains 0007;
- fresh baseline contains the unified table from the current manifest;
- SQLite legacy migration 17 creates it for legacy files;
- PostgreSQL repository performs `checkfirst` schema ensure for already-stamped 0007 environments.

The Alembic fresh-SQLite baseline test passes after this correction.

## Browser runtime bridge

A Headless Chromium test executed the real H5 JavaScript. Because direct localhost navigation is blocked by the execution environment's browser administrator policy, browser `fetch` was bridged to the live FastAPI process while preserving the real `ApiAdapter` request/response contract.

Validated persisted entities:

```text
Evidence       PASS
Artifact       PASS
Task           PASS
User           PASS
Job            PASS
Knowledge      PASS
Interview      PASS
Selected Job   PASS
```

A fresh independent browser page then pulled the FastAPI snapshot and restored all listed entities.

Granular `CareerOSServices.evidence.create()` → `ApiAdapter` → FastAPI entity CRUD was also verified.

JavaScript page/console errors during the runtime bridge test:

```text
0
```

## Runtime health

Validated application version:

```text
1.3.0-beta-unified-runtime
```

The application exposes approximately 155 registered routes in the tested build, including `/api/runtime/v1/*` runtime endpoints.

A successful local `/api/health` response is not equivalent to production certification. Runtime and Business E2E certificates remain environment-specific gates.
