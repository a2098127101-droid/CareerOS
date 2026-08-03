# CareerOS v1.5.1 Release-Hardening Test Report

Test date: 2026-07-27
Scope: local source regression plus disposable Docker staging infrastructure.

## Automated regression

- Python compileall: passed.
- Test files: 38.
- Pytest: **161 passed**, 1 dependency deprecation warning, 0 failed.
- Hashed-lock Docker image (`requirements.lock`): **161 passed**, 0 failed;
  warnings were the same TestClient notice plus a non-writable pytest cache.
- SQLite migration: **22/22**.
- Alembic head: `0010_immutable_runtime_tenant_hardening`.
- Published migration `0007` immutable SHA-256 guard: passed.
- Upgrade simulation from the original published `0007`: passed.
- OpenAPI cookie authentication scheme and canonical `/api/v1` aliases: passed.
- SSRF tests: passed with deterministic public-DNS isolation; no environment DNS dependency.
- Repository contract audit: 14 SQLite/PostgreSQL pairs, no missing public methods.
- Database access/DDL ownership audit: no unexpected direct-access module or split DDL.

The only pytest warning is Starlette's TestClient compatibility notice recommending
`httpx2`; it is not a test failure.

## Retrieval evaluation

The checked-in fixture under `data_samples/rag_eval_v1` is explicitly **Demo Data**.
It validates the deterministic local retrieval contract, not production relevance:

- cases: 3;
- Recall@5: 1.0;
- Recall@10: 1.0;
- MRR@10: 1.0;
- citation source accuracy: 1.0;
- authority accuracy: 1.0;
- effective-year accuracy: 1.0;
- required-term coverage: 1.0.

The tested local chain is Okapi BM25 plus SQLite FTS5 where available, with the
deterministic `local_hash` embedding fallback. Real semantic Embedding and remote
Reranker calls were **not tested**, because no credentials were available.

## Disposable staging infrastructure

Docker staging ran with a fresh project namespace and disposable volumes:

- PostgreSQL schema/repository certification: PASS;
- pgvector extension/vector column: PASS;
- Redis: PASS;
- distributed rate-limit state across independent clients: PASS;
- independent Redis worker execution: PASS;
- expired worker-lease recovery: PASS;
- MinIO private put/get/presigned-HTTP-get/delete round trip: PASS;
- forced PostgreSQL RLS metadata: PASS;
- non-superuser tenant A/B visibility probe: PASS (`rls-a` only for A, `rls-b` only for B).

This is an **infrastructure-only probe**, not a signed full Runtime Verified
certificate. Generation models, semantic Embedding, remote Reranker, external
observability, SMTP and public TLS/DNS were excluded.

## Browser E2E

Executed against the Docker-backed API in installed Chrome through Playwright:

- Student login and Coach message: PASS;
- workflow progress changed from 00/10 to 04/10: PASS;
- student workflow rendered without `undefined`: PASS;
- Teacher login and Operations Workspace: PASS;
- Super Admin login and Model & Knowledge Center: PASS;
- authenticated `/api/v1/admin/models/overview`: HTTP 200;
- browser console errors after the favicon fix: none on fresh Teacher/Admin sessions.
- standalone `file://` Showcase load and Student/Advisor/System switching: PASS,
  with explicit Demo labeling and no console/page errors.

Chrome was tested. Firefox and Safari were **not tested** in this environment.

## Not verified

- live OpenAI, DeepSeek, Claude, Gemini or Custom generation calls;
- live semantic Embedding provider;
- live Cohere/Jina/Voyage/compatible Reranker;
- external SMTP, observability collector, TLS, DNS, WAF or KMS;
- signed full runtime/business certification;
- production load/capacity and disaster-recovery targets.
