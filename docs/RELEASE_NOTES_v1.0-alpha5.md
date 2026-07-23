# Release Notes · v1.0-alpha5

## Theme

Model Governance + Identity Lifecycle + Privacy Foundation.

## Highlights

1. Model capability registry and capability-aware routing foundation.
2. Model evaluation harness with cost/latency/token metrics.
3. Native OpenAI-compatible streaming foundation with truthful fallback.
4. Tenant invitation lifecycle and user status/role management.
5. Privacy consent/version records and authenticated data export.
6. Auditable delete-request workflow.
7. PII minimization before third-party model calls.
8. Signed sandbox billing provider and idempotent webhook foundation.
9. SQLite migrations 13-14 and Alembic 0004-0005.
10. Showcase updated without introducing real personal identity data.

## Compatibility

- Existing SQLite local mode remains supported.
- Existing API surface is preserved; new generic/lifecycle/model APIs are additive.
- Existing Repository parity remains required.
- Showcase remains a standalone offline HTML.

## Production boundary

Alpha5 is not final Production Runtime. Live infrastructure certification and real external provider E2E remain separate release gates.

## Final verification

- 86 / 86 automated tests passed in the build environment.
- Repository contract parity: 12 / 12.
- Alembic head verified on fresh SQLite: `0005_billing_sandbox_foundation`.
- JavaScript syntax and Showcase source synchronization passed.
