# Architecture Debt Audit · v1.0-alpha7

## Improved in this release

| Area | Alpha7 result |
|---|---|
| Store-owned SQLite DDL | Removed from Store modules |
| Schema ownership audit | `CENTRALIZED`, zero Store-owned DDL violations |
| Direct SQLite CRUD | Retained only in 12 business compatibility modules; migration layer is the 13th direct-SQLite module |
| Workflow hard-coding | Default workflow preserved for compatibility, but five preset-aware templates now drive new instances |
| Artifact type restriction | Request model generalized; canonical template/alias resolver added |
| Job matching | Evidence-grounded requirement engine added |
| Claim verification overwrite | Replaced with persistent AI/human verification history |
| `main.py` modularization | Privacy + commercial/analytics routes extracted; paths unchanged |
| Repository contract | 12 pairs, zero missing public methods |

## Remaining debt

### `main.py`

Current composition module remains approximately 2.1k lines and still contains most API domains. Further extraction should proceed incrementally for model center, knowledge, jobs, workflow/artifacts/evidence and advisor/admin domains.

### SQLite compatibility layer

Twelve business compatibility modules still use direct `sqlite3` CRUD. This is intentional for local/offline compatibility, but business services should continue moving toward repository contracts so new domain logic never depends on SQLite-specific exceptions or SQL.

### Template engines

Alpha7 ships built-in preset-aware template engines. Full tenant-authored persistent template CRUD, visual editing, arbitrary transition expressions and custom renderer sandboxing are not yet complete.

### Job Intelligence

Current decomposition/matching is deterministic and conservative. Standard occupation/skill taxonomies, semantic normalization, external job ETL freshness/deduplication and benchmarked model-assisted decomposition remain future work.

### Evidence verification

History/human override is implemented, but true NLI/LLM entailment, confidence calibration and risk-based mandatory human review remain incomplete.

### Runtime certification

Live PostgreSQL/pgvector, Redis, object storage, embedding, LLM, observability, recovery and load testing are still the highest production blockers.
