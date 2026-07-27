# CareerOS v1.5 Changelog

## Added

- Persistent Claim, Claim Version and Claim relation models.
- Capability taxonomy/definition/version and Capability Assessment history.
- Requirement Version and Requirement–Capability Mapping.
- Career Gap and Gap Version lifecycle.
- Domain audit events.
- `/api/domain/v1` API.
- Unified H5 Domain Intelligence panels and explanation actions.
- PostgreSQL repository parity and Alembic `0009`.
- v1.5-specific regression tests.

## Changed

- Capability Profile in API mode is server-authoritative.
- Job Positioning distinguishes Potential Match, Verified Match and Evidence Coverage.
- Lexical overlap remains candidate support, not verified support.
- Evidence Trust fields are part of the canonical repository contract.
- Workspace AI routes are included in explicit rate-limit policies.

## Fixed

- PostgreSQL Evidence Trust repository parity.
- Requirement and Gap version-history persistence.
- Alembic seed binding on SQLite/PostgreSQL-compatible migrations.
- Historical tests that pinned the previous Alembic head or insecure self-verification semantics.
