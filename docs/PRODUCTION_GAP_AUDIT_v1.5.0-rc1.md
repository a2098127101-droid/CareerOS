# CareerOS v1.5.0-rc1 production gap audit

Audit date: 2026-08-03
Audit scope: `CareerOS-v1.5.0-pr13.zip`, release artifact, integration diagnostics, and the imported GitHub release branch.

## Executive decision

**NO-GO for opening production traffic.** The source package is suitable for a reviewable GitHub release candidate and local/staging verification, but the target server is not protocol reachable and the external-provider/runtime gates have not been certified. No runtime or business certification is asserted by this document.

## Evidence collected

- Main package SHA-256 matches the supplied checksum: `310ab8f10faf881318d22cf51583d58dae32b420ea0923fc588bd3e29ee0c109`.
- Package manifest declares no secrets, runtime database, or student data and explicitly says `runtime_verified: false`.
- Python compileall passed.
- Database-access audit passed with no unexpected direct-access module and centralized DDL ownership.
- Repository contract audit passed for 15 SQLite/PostgreSQL repository pairs.
- Local full pytest passed: **184 passed, 1 warning** after installing the package-declared `pytest-asyncio==1.4.0`.
- The package contains a linear Alembic chain through `0012_project_tenant_rls`; the package tests assert `0012_project_tenant_rls` as current.
- External cloud probes: ports 31569/31581/31582 accept TCP, but SSH returns no banner and HTTP requests to the application/file ports time out with zero bytes.

## P0 — blocks production traffic

| Finding | Evidence / location | Risk | Required remediation |
|---|---|---|---|
| Cloud runtime is unavailable at protocol level | External probe of 103.236.92.3:31569, :31581, :31582 | Cannot back up, migrate, start, or verify the application | Cloud-provider repair or host migration preserving the existing disk; then run the full deployment gate |
| Runtime/business certification is not present | Release manifest sets `runtime_verified` to false; package readiness docs exclude live provider and public TLS/DNS checks | A passing local suite could be misrepresented as production readiness | Execute target PostgreSQL/RLS, Redis/worker, MinIO, `/live`, `/ready`, student/teacher/admin E2E and signed runtime/business certificates |
| Real model-provider calls are unverified | `TEST_REPORT_v1.5.md` explicitly excludes live OpenAI/DeepSeek/Claude/Gemini, semantic embedding and remote reranker calls | AI output, fallback, latency, cost and PII controls are not certified | Configure production secrets through a secret manager and run provider, fallback, timeout, retry, token/cost and PII-redaction probes |
| Release identifiers are inconsistent in the supplied package | `VERSION.txt`, API version strings, README/test reports, and the supplied `pr13` manifest use different release labels | Rollback, audit, and artifact-to-deployment traceability can break | This branch normalizes the public release identifier to `v1.5.0-rc1`; build a new manifest, ZIP, checksum and tag from the final commit |

## P1 — required before a controlled university pilot

- Verify managed PostgreSQL with a dedicated non-owner, non-superuser, `NOBYPASSRLS` application role and a separate migration owner.
- Verify backup/restore, rollback, load smoke, disk/database/queue thresholds and encrypted off-host backup custody.
- Verify Caddy HTTPS, DNS, HSTS/security headers, WAF/egress policy, JSON logs and monitoring/alerting.
- Run Chromium, Firefox and WebKit authorization/concurrency coverage, including cross-tenant negative cases and mobile smoke.
- Certify SMTP/email delivery, private object storage, signed download URLs and malware scanning in the target environment.
- Replace the three-case Demo retrieval fixture with an adjudicated multilingual evaluation set with hard negatives; run real semantic embedding and remote reranker evaluation.
- Add server-side pagination/filter/sort for large student, evidence, artifact and job catalogs.

## P2 — product hardening after pilot gate

- Modular TypeScript frontend migration; accessibility, keyboard and RTL audit.
- Taxonomy administration, deprecation/merge workflows, requirement approval and evidence-recency policies.
- Production DOCX/PDF/PPTX rendering and complete offline replay.
- Daily/monthly AI budgets, provider concurrency controls and pricing records for all configured models.

## Scope-preservation check

The imported package retains the backend, Multi-Model Gateway, RAG/retrieval layer, Structured Job Store, Evidence Ledger/Graph, Artifact Versioning, Teacher Feedback and AI Task Center, 10-stage workflow, Windows launcher, and standalone H5 Showcase. No production capability was replaced with a static mock or removed as part of this audit.

## Next gate

After the server is repaired, deploy only from the final tagged commit and record: commit SHA, image digest, Alembic head, database fingerprint, runtime certificate, business certificate, ZIP SHA-256, SBOM and deployment timestamp. Until all P0 and pilot P1 gates are evidenced, the correct status remains **NO-GO**.
