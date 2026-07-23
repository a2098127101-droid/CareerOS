# Architecture Debt Status · v1.0-beta1

## Reduced

- Store-owned DDL violations: **0**.
- Schema ownership remains centralized in compatibility migrations/Alembic.
- Repository public contract: **12/12 pairs, 0 missing methods**.
- New beta1 certification/worker modules add no new direct SQLite business coupling.
- Worker startup no longer depends on importing FastAPI `app.main`.
- Runtime model certification uses the selected RepositoryContainer backend.

## Remaining

### Legacy SQLite compatibility CRUD

12 legacy business modules still directly use `sqlite3` as the local compatibility implementation. This is intentional for the local/offline runtime but should gradually become explicit SQLite Repository adapters behind the same interfaces.

### `app/main.py`

The composition module remains large. Privacy, commercial and template routes have already been split, but Auth, Participant/Advisor, Workflow/Artifact/Evidence, Knowledge, Jobs, Models, Files and Runtime routes still need gradual router/service extraction.

### Configurable engines

Tenant Workflow and Artifact registries support persistent versioned activation, but not yet a complete conditional Workflow Rule Engine, visual builder or schema-driven renderer/editor ecosystem.

### Evidence intelligence

Risk governance and verification history exist, but full NLI/entailment and calibrated human-review policy remain incomplete.

### Enterprise/commercial

Real Billing Providers, SSO, bulk provisioning, full retention-policy engine and formal SLA/multi-region operations remain outside beta1 certification.
