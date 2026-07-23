# Commercial Deployment Readiness

## Implemented foundations

- Authentication / RBAC / tenant foundation.
- Multi-model routing and fallback.
- Retry/backoff/circuit-breaker foundation.
- Evidence Graph and artifact traceability.
- Persistent workflow.
- Hybrid retrieval architecture.
- Pluggable semantic embedding interface.
- Local/S3-compatible storage adapter foundation.
- Plans, entitlements, quotas and analytics event foundation.
- Production Readiness diagnostics.

## P0 before public multi-instance SaaS

1. Migrate the operational repository layer from SQLite to PostgreSQL.
2. Use pgvector or another production vector backend for semantic embeddings.
3. Complete private object download / signed URL authorization and malware scanning hooks.
4. Add Redis-backed distributed rate limiting and background jobs for indexing/batch review.
5. Add error monitoring, metrics and tracing.
6. Configure real production secrets and provider credentials.
7. Add backups, restore drills and migration rollback procedures.

## Billing status

Plans and entitlements exist, but billing is `foundation/mock`. Do not market the release as having live payment processing until a real BillingProvider, webhook verification and order/subscription records are implemented and tested.

## Production Readiness API

`GET /api/admin/system/readiness`

This endpoint intentionally reports unresolved blockers instead of presenting configuration placeholders as completed infrastructure.
