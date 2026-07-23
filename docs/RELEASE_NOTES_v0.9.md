# Release Notes v0.9

This release generalizes CareerOS for broad commercial reuse and adds production-runtime foundations without removing existing AI/RAG/traceability capabilities.

Major additions:

- Product Presets and tenant type.
- Neutral generic demo personas/content.
- Commercial plans, entitlements, quotas and analytics events.
- Embedding Provider interface.
- S3-compatible storage adapter foundation.
- Retry/backoff/circuit-breaker foundation.
- Production Readiness diagnostics.
- Generic Admin commercialization workspace.

Known production blocker: the operational repository layer remains SQLite. PostgreSQL migration is the next P0.

## Verification

- 37 Python tests passed.
- All primary inline JavaScript bundles passed syntax checks.
- Standalone and server Showcase files are synchronized.
- Clean-database smoke test confirmed generic Product Preset, generic artifact generation, commercial overview and readiness diagnostics.
