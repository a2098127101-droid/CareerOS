# CareerOS v1.5 Test Report

## Result

- Test files: 36
- Automated tests: **153/153 passed**
- CI Group 0: 16 passed
- CI Group 1: 23 passed
- CI Group 2: 21 passed
- CI Group 3: 18 passed
- CI Group 4: 37 passed
- CI Group 5: 38 passed

Warnings: Python 3.13 SQLite datetime-adapter deprecation warnings only; no functional failures.

## v1.5-specific coverage

- fresh SQLite schema and global capability seed;
- fresh Alembic upgrade to `0009_domain_intelligence_v15`;
- Claim extraction from Evidence and Artifact Versions;
- persistent Claim–Evidence and Claim–Capability relations;
- persistent Requirement snapshots and Requirement–Capability mappings;
- Potential versus Verified Assessment values;
- Evidence verification changes Verified Assessment results;
- capability explanation chain;
- Claim, Requirement, Assessment and Gap version histories;
- Claim and Gap optimistic-lock conflicts;
- domain audit events;
- SQLAlchemy/PostgreSQL repository contract exercised on SQLAlchemy SQLite;
- existing Evidence, Artifact, Workflow, RAG, Provider, tenancy and runtime regressions.

## Additional checks

- Python compileall: passed.
- H5 inline JavaScript syntax: passed.
- H5 standalone/static copy equality: passed.
- Repository contract audit: passed for 14 SQLite/PostgreSQL pairs.
- Database-access/DDL ownership audit: passed with no unexpected modules or split DDL.
- Fresh SQLite migration: 21/21.
- Fresh Alembic upgrade: `0009_domain_intelligence_v15`.
- FastAPI health/live/ready: HTTP 200; 201 registered routes.
- ZIP integrity and SHA-256: verified at release packaging.
