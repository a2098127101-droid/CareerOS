# Release notes · CareerOS v1.0-alpha1

This is a production-data-foundation release, not the final v1.0 Production Runtime.

### Added
- Repository interface package and dependency container.
- SQLAlchemy/Alembic baseline architecture.
- PostgreSQL schema manifest and generated DDL.
- Migration snapshot export/import/verification tools.
- First SQLAlchemy session repository parity adapter.
- Generic canonical role compatibility layer.
- Generic participant profile compatibility model.
- `enterprise_talent` preset.
- Generic route aliases for participant/advisor/group terminology.
- Repository diagnostics endpoint.

### Preserved
- SQLite local runtime and existing data compatibility.
- Existing API routes.
- Auth/RBAC/tenant foundation.
- Agents, model gateway, Evidence Graph, Workflow, Artifact Traceability, RAG and Showcase.

### Explicitly NOT READY
- Full PostgreSQL runtime repository parity.
- Live PostgreSQL integration verification.
- pgvector.
- Redis/background jobs.
- Private signed-download lifecycle.
- Production billing.
- Full semantic evidence entailment.
