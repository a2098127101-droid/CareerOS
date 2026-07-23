CareerOS v1.0-alpha8 · Tenant Configurability & Governance

QUICK DEMO
1. Open CareerOS_H5_Showcase.html directly in a modern browser.
2. It is a standalone anonymous Demo Scenario and uses no real API key, payment service, database, or backend.

LOCAL APPLICATION
- Windows: double-click OPEN_CareerOS.cmd
- Default development database: SQLite compatibility runtime
- Default runtime state: memory
- Default background jobs: in-process
- Default storage: private local files with signed access
- Default embedding provider: local_hash (offline fallback; NOT semantic embedding)
- Default email provider: console outbox (NOT external delivery)

ALPHA8 MAIN CHANGES
- Tenant-authored, versioned Workflow Templates with activation semantics
- Tenant-authored Artifact Templates with schema/renderer/rubric metadata
- High-risk Evidence Governance and mandatory human-review signaling
- Background-job idempotency + lease/heartbeat/dead-letter foundations
- Template administration routes extracted into a dedicated router module
- Migration 16 / Alembic 0007 and 44-table schema manifest
- Existing Repository, RAG, Runtime, Identity, Privacy, Model Governance and Billing foundations retained

IMPORTANT
This is NOT final Production Runtime.
Live PostgreSQL + pgvector, Redis multi-instance runtime, S3-compatible storage, semantic embedding, real generation LLM E2E, live observability exporters, PostgreSQL backup/restore drill and real staging load certification remain NOT VERIFIED until executed in the target environment.
