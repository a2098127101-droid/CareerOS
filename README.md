# CareerOS v1.0-beta1 · Business Runtime Verification Candidate

[English](README.md) | [简体中文](README.zh-CN.md)

> **Pre-release notice:** this repository is a verification candidate, not a production-ready or Runtime Verified release.

CareerOS is an AI-native **Career Development & Talent Intelligence Platform** with two maintained delivery tracks:

- **Showcase Edition** — one anonymous standalone HTML file; no backend, database, payment service, or API key.
- **Production Edition** — FastAPI, authentication/RBAC/multi-tenant isolation, multi-Agent runtime, multi-model gateway, Hybrid RAG, Evidence Graph, Workflow/Artifact templates, Job Intelligence, privacy/runtime infrastructure, analytics and commercialization foundations.

## What beta1 changes

beta1 upgrades acceptance from **component connectivity** to **business-runtime verification**. A deployable staging harness can now prove whether the configured environment actually supports the CareerOS business path rather than merely whether PostgreSQL/Redis/S3/model endpoints respond.

### Business E2E certification

A signed, environment-bound, freshness-limited business certificate exercises:

```text
Authenticated participant
→ Session
→ Profile Agent
→ Coach
→ Private file upload
→ Writer / Artifact V1
→ Reviewer
→ Evidence verification
→ Critic + Revision / Artifact V2
→ Artifact trace
→ Cross-tenant attack suite
→ LLM usage proof
```

Certification users use ephemeral random credentials and are de-identified/archived during cleanup. A known default certification password is never left in the target database.

### Semantic RAG quality gate

The business certificate also seeds temporary conflicting/current knowledge and requires:

- current-year retrieval,
- authoritative-source selection,
- `Recall@5` success for the certification case,
- no cross-tenant knowledge leakage,
- a real semantic provider rather than `local_hash`.

### Independent worker and recovery certification

Runtime certification no longer self-executes a queued job inside the certifier process. A PASS requires an **independent worker process/container** to consume the Redis job. The gate also simulates an expired worker lease and requires stale-job recovery plus independent execution.

### Private object HTTP verification

S3-compatible certification now performs:

```text
PUT
→ SDK GET + SHA256
→ presigned URL
→ real HTTP GET + SHA256
→ DELETE
```

Generating a presigned URL alone is no longer considered sufficient evidence.

### Migration and disaster-recovery drills

beta1 adds non-destructive staging certification harnesses for:

- realistic SQLite fixture → snapshot → temporary PostgreSQL database → Alembic → import → verification → Repository read-back,
- temporary PostgreSQL schema → `pg_dump` → drop → `pg_restore` → data-integrity read-back.

### Signed release gates

`/ready` in production now requires both:

- a valid **Runtime Certification**, and
- a valid **Business E2E Certification**.

Certificates are HMAC signed, environment-bound and time-limited.

### Staging gate

`deploy/docker-compose.staging.yml` provides a PostgreSQL+pgvector, Redis, MinIO, API, worker and certifier topology. `scripts/staging_runtime_gate.py` gates on:

1. preflight,
2. Alembic,
3. PostgreSQL Repository certification,
4. Runtime certification,
5. Business E2E certification,
6. SQLite→PostgreSQL migration drill,
7. PostgreSQL backup/restore drill,
8. measured HTTP smoke/load gate,
9. `/live` and `/ready`.

## Local start

Windows:

```text
OPEN_CareerOS.cmd
```

Cross-platform:

```bash
python -m venv .venv
pip install --require-hashes -r requirements.lock
python -m uvicorn app.main:app --reload
```

Offline Showcase:

```text
CareerOS_H5_Showcase.html
```

## Status

**This build is not claimed as Runtime Verified.** The current build environment does not provide Docker, a live PostgreSQL/pgvector instance, Redis, MinIO/S3, real semantic embedding credentials, or a real generation-model credential. The corresponding harnesses are implemented, but live certification remains `NOT VERIFIED` until executed in a real staging environment.

The P0 stabilization fixes the route test's dependency on FastAPI's former flat internal route list, forces cross-platform LF snapshot bytes, counts pytest 9 results through a reporting hook, and adds a hash-locked dependency graph. The corresponding [GitHub Actions run](https://github.com/a2098127101-droid/CareerOS/actions/runs/29988693142) passed **132/132 tests** across 32 isolated test files on Python 3.11.9.

The release remains a pre-release because live PostgreSQL/pgvector, Redis, MinIO/S3, semantic embeddings, generation models, and the complete staging certification are still not verified. See `docs/TEST_REPORT_v1.0-beta1.md` for the packaged and current verification records.

Primary operational documentation:

- `deploy/README_BETA1_STAGING.md`
- `docs/BUSINESS_E2E_CERTIFICATION_v1.0-beta1.md`
- `docs/MIGRATION_RECOVERY_CERTIFICATION_v1.0-beta1.md`
- `docs/WORKER_RECOVERY_v1.0-beta1.md`
- `docs/TEST_REPORT_v1.0-beta1.md`

## License

This repository is governed by the proprietary CareerOS license in `LICENSE`.
The source is publicly viewable for evaluation and review only; no right to
use, copy, modify, deploy, or distribute it is granted without prior written
permission from the copyright holder. This project is not represented as
open-source software.
