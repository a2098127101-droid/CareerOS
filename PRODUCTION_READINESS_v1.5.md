# CareerOS v1.5 Production Readiness

## Completed and regression-tested

- Persistent/versioned Claim, Capability Assessment, Requirement Snapshot and Gap models.
- Explainable Potential/Verified scoring and contribution records.
- Domain audit events and optimistic locking for Claim/Gap changes.
- Evidence Trust separation between self-reported and verified evidence.
- SQLite and SQLAlchemy/PostgreSQL repository paths.
- Canonical API and Unified H5 consumption.

## Requires target-environment verification

- Real PostgreSQL deployment and backup/restore drill.
- Redis/distributed rate limiting and independent workers.
- S3/MinIO object storage.
- Real LLM/embedding/provider credentials.
- SMTP/email provider.
- TLS, DNS, WAF, egress policy, monitoring and alerting.
- Playwright multi-role browser matrix in staging.

## Release recommendation

Suitable for source publication, internal Beta and staging. Do not market the deterministic Capability score as a validated assessment. Do not claim production certification until the infrastructure and staging gates above pass.
