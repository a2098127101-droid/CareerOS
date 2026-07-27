# CareerOS v1.4 — Canonical Runtime Architecture

## Runtime principle
Business truth must live in canonical domain stores, not browser state or a generic JSON table.

```text
Unified H5 / future modular UI
        ↓
Feature Services / DataAdapter
        ↓
FastAPI Workspace BFF + domain APIs
        ↓
Canonical services
 ├ Identity / Tenant / Membership
 ├ Evidence + Evidence Graph
 ├ Artifact + Artifact Versions
 ├ Collaboration Tasks
 ├ Knowledge / Parser / Hybrid Retrieval
 ├ Job Intelligence / Matching
 └ ModelGateway / Providers
        ↓
SQLite (development) / PostgreSQL (production target)
```

`unified_runtime_entities` is retained only for generic UI/runtime state such as settings, notifications, chat/session cache, usage UI events and selected-job UI state. Canonical Evidence, Artifact, Task, User, Knowledge and Job writes are rejected through legacy generic collection APIs.

## Concurrency
Evidence, Artifact and Task expose versions. Stale updates/deletes return HTTP 409 rather than silently overwriting newer data.

## Multi-user isolation
Runtime generic identity includes tenant + owner. Staff access to another participant requires an explicit subject and authorization. Advisor access requires a shared class relationship; organization admins are tenant-scoped.

## AI runtime
API-mode AI Coach, Interview and PPT Review call `ModelGateway`; provider/model routing remains vendor-neutral. Missing routes are explicit errors, not deterministic fake AI.

## Data migration
- SQLite migrations: 1–19.
- Alembic head: `0008_canonical_runtime_consistency`.
- Schema manifest and PostgreSQL baseline are generated from the current migrated schema.
