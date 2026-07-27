# CareerOS v1.4 Test Report

## Automated regression
35 test files were executed in three non-overlapping groups due the current environment's long single-process timeout behavior.

- Group 1: 43 passed
- Group 2: 35 passed
- Group 3: 70 passed
- Total: **148 / 148 passed**

Coverage includes legacy API compatibility, authentication/tenant isolation, Evidence Graph, workflow, knowledge/RAG, repository parity, PostgreSQL certification helpers, model/provider governance, billing/privacy, runtime certification foundations, v1.3 compatibility, and v1.4 canonical runtime tests.

## v1.4-specific assertions
- Same entity ID across different owners does not collide.
- Staff cannot tenant-wide replace canonical participant collections.
- 5,001 runtime rows are returned without a 5,000-row truncation.
- Evidence/Artifact/Task stale mutations return conflicts.
- Task stale delete is rejected.
- Same-kind artifacts remain independent series and versions increment correctly.
- Advisor access requires an explicit shared class relationship.
- Provider SSRF and plaintext-secret guards reject unsafe configurations.
- AI Coach/Interview do not fabricate API-mode results when model routes are unavailable.
- CI is no longer locked to a historical fixed test count.

## Static/runtime checks
- `python -m compileall -q app scripts tests`: PASS.
- H5 inline JavaScript syntax (`node --check`): PASS.
- Standalone/server Showcase byte-for-byte synchronization: PASS.
- FastAPI version: `1.4.0-beta-canonical-runtime`.
- Registered routes: 184.
- Local development smoke: `/api/health`, `/live`, `/ready`, `/api/workspace/v1/context` HTTP 200.
- SQLite migration current/latest: 19/19.

## Browser E2E boundary
Headless Chromium in this container failed to initialize to a usable DOM because of container D-Bus/zygote constraints and was terminated after 15 seconds. No complete browser E2E claim is made. A Playwright suite should run in GitHub/staging on a supported browser runner before production release.
