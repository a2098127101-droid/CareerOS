# CareerOS v1.4 Remaining Gaps and Next Development Priorities

## P0 before commercial production
1. **Target-environment infrastructure certification**: real PostgreSQL, Redis, independent workers, S3/MinIO, backups and restore drills.
2. **Browser E2E in supported CI/staging**: multi-role workflows, multi-tab conflicts, upload flows and all supported languages.
3. **Production authentication/security hardening**: SSO/OIDC/SAML as needed, MFA policy, secure-session/CSRF review, WAF/rate limits, KMS secrets, penetration test.
4. **Canonical domain completion**: move capability scoring/gap derivation from remaining client heuristics into server domain services.

## P1 product/engineering
1. Modularize the 280KB+ monolithic H5 into TypeScript feature modules/components; remove legacy monkey-patch/event interception layers.
2. Add optimistic locking/versioning to Knowledge/Job admin catalogs and a real server-side audit/restore model.
3. Complete offline mutation queue for multipart/file operations and deterministic conflict resolution UI.
4. Build native DOCX/PDF/PPTX rendering/export services.
5. Finish key-based i18n for all strings, validation/errors/date/number/currency and RTL QA.
6. Persist chat attachments in object storage and connect parsed contents to RAG/AI context.
7. Add real organization/department/cohort/advisor assignment scopes beyond class relationship checks.

## P2 scale/operations
- Cursor pagination and virtualized UI for large job/knowledge/user datasets.
- OpenTelemetry traces, SLO dashboards, cost budgets and alerting.
- Provider egress allowlists and per-provider quotas.
- Load/chaos testing and disaster-recovery exercises.
- Formal API version/deprecation policy and generated OpenAPI SDKs.
