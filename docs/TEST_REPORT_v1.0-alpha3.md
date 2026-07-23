# Test Report — CareerOS v1.0-alpha3

## Summary

All 68 collected tests passed across three isolated test batches.

```text
Batch 1: 25 passed
Batch 2: 28 passed, 11 warnings
Batch 3: 15 passed
Total:   68 / 68 passed
```

A single monolithic pytest orchestration reached 97% but the orchestration command timed out before its final summary; it is not used as evidence. The 68-test result is based on the three completed isolated batches above.

## New alpha3 coverage

### Semantic RAG

- Migration 11 schema changes.
- Alembic revision 0002 presence and SQLite upgrade compatibility.
- Embedding metadata persistence.
- Truthful remote-provider fallback to local_hash.
- Deterministic RAG evaluation metrics.
- API integration for knowledge ingest + evaluation.

### Evidence Verification

- Numeric claim consistency behavior.
- Conservative verification behavior.
- Persistent claim verification fields.
- Evidence verification API integration.

### Repository / compatibility

- Alpha2 repository parity and certification tests retained.
- Repository contract audit remains 12/12 with zero missing public methods.
- Existing Auth/RBAC/Tenant, Artifact, Workflow, Evidence Graph, Showcase and genericization regression tests retained.

## Warnings

11 warnings arise from Python 3.13 / SQLite datetime adapter deprecation paths in SQLAlchemy-backed test fixtures. They are warnings, not test failures.

## Additional checks

- Python compileall: PASS.
- Repository contract audit: PASS, 12/12 repository pairs, missing methods 0.
- Alembic fresh SQLite upgrade to `0002_semantic_rag_pgvector`: PASS.
- Generic/personal-data release scan: no known personal identity, school, major or personal research sample strings found.
- Showcase standalone file and server `/showcase` copy kept synchronized.

## Explicitly not verified

- Live PostgreSQL connection/integration.
- Live pgvector query execution.
- Real semantic embedding provider with real credentials.
- Real LLM provider E2E.
- Redis/background jobs.
- Windows physical execution in this Linux build environment.
- Safari/Firefox physical browser verification.
