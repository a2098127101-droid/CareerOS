# StepIn 2.2 Deployment Readiness

StepIn 2.2 has a production-oriented engineering baseline, but public or institutional deployment still requires environment-specific evidence. This document replaces the obsolete pre-PostgreSQL readiness assumptions from earlier CareerOS builds.

## Implemented production foundations

- authentication, role and tenant isolation foundations;
- PostgreSQL/SQLAlchemy repository path with migration and RLS certification requirements;
- Redis-backed worker/runtime foundations;
- private S3-compatible object-storage path;
- model routing, fallback and usage/cost governance foundations;
- semantic retrieval infrastructure;
- Evidence/Artifact traceability and immutable project-template versions;
- StepIn Foundation, Learner Agent, Learner Trajectory and bounded Policy Calibration;
- production readiness endpoints, audits, supply-chain scanning and deterministic release packaging.

## P0 before public pilot traffic

The remaining P0 work is verification rather than a claim that infrastructure is absent: certify the actual PostgreSQL/RLS role, Redis persistence and recovery, private object delivery, real model/retrieval routes, student/teacher StepIn E2E, cross-tenant negative access, monitoring, load smoke, backup/restore and rollback on the target environment. Institution-approved privacy, consent/authorization, retention and support ownership must also be in place.

Windows x64 install/offline/upgrade/backup-restore remains a separate release gate until tested on real Windows hardware.

## Product-validity boundary

Engineering readiness does not prove educational effectiveness. Capability Verification 2.0, real-work-sample quality and policy calibration still require real learner trajectories, repeated cross-task evidence and human labels. Do not market completion, capability confidence or Agent diagnosis as independently validated educational certification without that evidence.

## Current authoritative checks

Use `TEST_REPORT.md`, `SECURITY.md`, `deploy/README_PRODUCTION.md` and `deploy/PRODUCTION_CHECKLIST.md`. `GET /api/admin/system/readiness`, `/live` and `/ready` are runtime signals, not substitutes for the full go-live checklist.
