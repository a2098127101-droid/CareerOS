# CareerOS v1.5 Production Readiness

## Completed and regression-tested

- Persistent/versioned Claim, Capability Assessment, Requirement Snapshot and Gap models.
- Explainable Potential/Verified scoring and contribution records.
- Domain audit events and optimistic locking for Claim/Gap changes.
- Evidence Trust separation between self-reported and verified evidence.
- SQLite and SQLAlchemy/PostgreSQL repository paths.
- Canonical API and Unified H5 consumption.
- Forward-only migration `0010` repairs the historical migration split without
  mutating the published `0007`.
- Tenant-first indexes and forced PostgreSQL RLS policies on tenant-private tables.
- Real disposable infrastructure probe for PostgreSQL/pgvector, Redis/worker and MinIO.
- Chrome Student/Teacher/Super-Admin E2E and authenticated `/api/v1` model-admin API.

## Requires target-environment verification

- Managed/target PostgreSQL deployment, dedicated non-owner application role,
  backup/restore and load drill.
- Real LLM, semantic Embedding and remote Reranker credentials.
- SMTP/email provider.
- TLS, DNS, WAF, egress policy, monitoring and alerting.
- Firefox/Safari and authorization-concurrency browser matrix.

## Release recommendation

Suitable for source publication, internal Beta and staging. Do not market the
deterministic Capability score as a validated assessment. The successful
infrastructure-only probe must not be represented as full production
certification.
