# CareerOS v1.5.0-rc1 Domain Intelligence — Release Notes

## Release focus

CareerOS v1.5 promotes the career-intelligence chain into persistent canonical server entities:

```text
Evidence / Artifact
  → Claim
  → Capability Assessment
  → Job Requirement Mapping
  → Career Gap
```

Every central object now has dedicated storage, version history, explainability data and audit events.

## Main additions

- persistent Claims and Claim Versions;
- Claim–Evidence and Claim–Capability links;
- versioned Capability definitions and assessment history;
- versioned Job Requirement snapshots and capability mappings;
- versioned Career Gaps with lifecycle state and optimistic locking;
- Potential Score and Verified Score separation;
- contribution-level explanations and Domain Audit Events;
- `/api/domain/v1` API and H5 API-mode integration;
- SQLite and SQLAlchemy/PostgreSQL repository parity;
- migrations 21/22 plus project migrations, with Alembic head `0012_project_tenant_rls`.

## Validation

- 36 test files;
- 184/184 automated tests passed in six deterministic CI groups;
- 14 SQLite/PostgreSQL repository contracts audited;
- fresh SQLite and Alembic migrations passed;
- H5 JavaScript syntax and static-copy equality passed;
- FastAPI health/live/ready passed with 201 registered routes.

## Release boundary

The v1.5 assessment methodology is a deterministic, explainable evidence-coverage model. It is not a psychometric instrument, professional certification or validated job-performance predictor. Production infrastructure and browser staging certification remain separate gates.
