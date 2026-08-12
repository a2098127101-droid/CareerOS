# StepIn 2.2 Test Report

## Current locked baseline

The current production line is `2.2.0-beta-agent-trajectory`. The StepIn CI contract enforces **204 / 204 automated tests** and fails if the locked count or any regression batch does not pass.

The latest StepIn 2.2 production baseline before this documentation cleanup passed the locked matrix on `main`. This cleanup does not reduce the test contract; the same 204-test gate remains authoritative for subsequent commits.

## StepIn-specific production gates

- Learner Agent contract audit: 13 API routes, fixed action/tool boundaries, trajectory enabled and human-activated calibration.
- Foundation production contract: 10 routes and beginner-gate behavior.
- Project Library v2.2 audit: current immutable library version, practice-first structure and agent-observable metadata.
- Real Trajectory integration: learner practice events, revision, transfer, teacher feedback, Evidence decisions, project milestones and Agent interventions.
- Policy Calibration boundary: candidate profiles are range-limited and require explicit administrator activation.

## Retained platform regression gates

- Python application, migration and test compilation.
- Deployment shell syntax and production Compose validation.
- Database-access boundary audit.
- Repository-contract audit across supported repository implementations.
- Tenant and authorization regressions.
- Evidence, Artifact, project, worker, storage, RAG/provider and production-runtime regressions retained by the current test matrix.
- Dependency consistency, supply-chain scanning and release-package boundary checks.

## Release boundary

Passing CI establishes source-code and engineering-contract consistency. It does not by itself certify educational effectiveness, a specific external model provider, a target cloud environment, Windows x64 installation/offline behavior, or institutional privacy/operational readiness. Those remain separate validation gates.
