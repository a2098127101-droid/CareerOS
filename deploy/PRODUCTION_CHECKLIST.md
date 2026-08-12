# StepIn 2.2 Pilot Go-Live Checklist

Use this checklist for the current controlled StepIn pilot. Every completed item should point to verifiable evidence such as a CI run, configuration review, runtime certificate, test report, backup artifact or named owner.

## Release integrity

- [ ] Deploy a reviewed StepIn commit or release tag, not a working branch.
- [ ] StepIn CI passes the locked **204-test** matrix.
- [ ] Learner Agent, Foundation and Project Library v2.2 audits pass.
- [ ] Dependency, secret, filesystem and container scans pass.
- [ ] Production Compose validates.
- [ ] `StepIn-*` release ZIP checksum and manifest verify.

## Identity, tenancy and data infrastructure

- [ ] `DEMO_MODE=false` and `AUTH_REQUIRED=true`.
- [ ] Student, teacher/advisor, organization administrator and platform administrator permissions are tested separately.
- [ ] Cross-tenant object access fails without information leakage.
- [ ] PostgreSQL is the active production repository and Alembic is at the reviewed head.
- [ ] Application connection uses a non-owner, non-superuser, `NOBYPASSRLS` role.
- [ ] Redis authentication/persistence and independent worker execution/recovery are verified.
- [ ] MinIO/S3 storage is private and presigned retrieval works.
- [ ] PostgreSQL, Redis and object-storage API ports are not publicly exposed.

## AI, retrieval and Learner Agent

- [ ] Required generation provider routes and fallbacks are configured and tested.
- [ ] A real embedding/retrieval path is configured and evaluated on pilot-appropriate material.
- [ ] Unknown model prices remain unpriced rather than being treated as zero-cost.
- [ ] PII/data-minimization and retention settings match the published privacy notice.
- [ ] Learner Agent cannot bypass Foundation/Project gates, Evidence verification or authorization.
- [ ] Candidate Policy Calibration profiles require sufficient trajectory data and explicit administrator activation.

## Current learner business flow

- [ ] A beginner can enter Foundation without first choosing a target job or completing a career assessment.
- [ ] A real simple task can be opened, understood and completed with source material visible.
- [ ] ASK / HINT / EXPLAIN support is bounded and does not generate the learner's final deliverable.
- [ ] Failure, help requests, completion and revision events enter Learner Trajectory.
- [ ] The learner can revise a first version after feedback without overwriting process history.
- [ ] A transfer task uses different material and records independent performance.
- [ ] Evidence/Artifact records preserve the relevant process and version history.
- [ ] A new practice project uses the current immutable Project Library v2.2 template.
- [ ] Project milestones and teacher feedback enter the trajectory.
- [ ] The learner cannot be marked as stably capable from a single completion event alone.

## Teacher / human-review flow

- [ ] Teachers see only authorized learners/groups.
- [ ] Teacher view exposes relevant failure, hint, revision, transfer and Evidence context.
- [ ] Human review can override or annotate Agent diagnosis where supported.
- [ ] Teacher feedback and feedback-resolution events persist.
- [ ] Human escalation works when the Agent reaches its policy boundary.

## Governance, privacy and operations

- [ ] AI calls, latency, tokens, errors and model identity are auditable.
- [ ] Policy profile changes and activation are auditable.
- [ ] Real learner data is absent from demo/test tenants.
- [ ] Institution-approved privacy notice, consent/authorization and retention rules are published.
- [ ] Export/deletion requests, incident response and support escalation have named owners.
- [ ] Raw learner trajectories are not reused across tenants for research/model training without separate authorization and de-identification.

## Backup, restore and observability

- [ ] Encrypted off-server PostgreSQL backup succeeds and checksum verifies.
- [ ] Restore has been tested in an isolated environment.
- [ ] Previous reviewed release remains available for rollback.
- [ ] `/live` and `/ready` return HTTP 200 after all required dependencies and certificates are healthy.
- [ ] Monitoring receives controlled test events and alerts reach named recipients.
- [ ] Pilot load-smoke passes on the actual target environment.

## Separate Windows x64 release gate

- [ ] Fresh install on real Windows x64 hardware.
- [ ] First launch and Foundation/Learner Agent flow.
- [ ] Full offline use where promised.
- [ ] Save, restart and data persistence.
- [ ] Export and backup.
- [ ] Upgrade and data migration.
- [ ] Restore.
- [ ] Uninstall/reinstall without unintended data loss.

Public pilot traffic should open only when mandatory target-environment items are evidenced. Linux GitHub Actions and container startup do not substitute for Windows certification or real-environment go-live evidence.
