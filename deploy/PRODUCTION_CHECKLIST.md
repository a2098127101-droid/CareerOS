# StepIn 2.2 Pilot Go-Live Checklist

Use this checklist for the current controlled StepIn pilot. Every completed item should point to verifiable evidence such as a CI run, configuration review, runtime certificate, test report, backup artifact or named owner. Canonical source/release identity is defined in `config/stepin_release_baseline.json`.

## Release integrity

- [ ] Deploy a reviewed StepIn commit or release tag, not a working branch.
- [ ] StepIn CI passes the canonical **208-test** locked matrix.
- [ ] `scripts/audit_release_baseline.py` passes and public docs match the canonical baseline.
- [ ] Frontend package-lock zero-drift and deterministic `npm ci` pass.
- [ ] Root Docker multi-stage build compiles the Spatial frontend from source and contains `/app/app/static/app/index.html` in the final runtime image.
- [ ] Learner Agent, Foundation, Project Library v2.2 and repository/database audits pass.
- [ ] Dependency, secret, filesystem and container scans pass.
- [ ] Production Compose validates.
- [ ] `StepIn-*` release ZIP checksum and manifest verify.
- [ ] Release manifest embeds the exact `config/stepin_release_baseline.json` content.
- [ ] Release boundary still reports `runtime_verified=false` and `windows_webview2_certified=false` until corresponding certification evidence exists.

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
- [ ] Capability Verification does not promote from a single completion event or frontend interaction alone.
- [ ] At least one verified-capability case is traced end-to-end from task contexts through transfer and canonical verified Evidence.
- [ ] A new practice project uses the current immutable Project Library v2.2 template.
- [ ] Project milestones and teacher feedback enter the trajectory.

## Spatial Practice runtime

- [ ] `/app` boots from the final deployed runtime image rather than a host-side development bundle.
- [ ] `/app?quality=auto` selects a render budget and remains usable on target hardware.
- [ ] `ultra / high / balanced / safe` overrides boot without uncaught WebGL errors.
- [ ] WebGL context-loss handling falls back to Safe and does not mutate learning state.
- [ ] `/app?demo=1` is clearly marked as visual rehearsal and does not create Evidence, Artifact, Capability or Trajectory events.
- [ ] Target device FPS/frametime, context-loss and automatic downgrade observations are recorded separately from learner content.

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
- [ ] Performance telemetry excludes Evidence text, learner answers, uploaded private material and other learning-content payloads.

## Backup, restore and observability

- [ ] Encrypted off-server PostgreSQL backup succeeds and checksum verifies.
- [ ] Restore has been tested in an isolated environment.
- [ ] Previous reviewed release remains available for rollback.
- [ ] Rollback preserves persistent data and restores a known-good Spatial bundle.
- [ ] `/live` and `/ready` return HTTP 200 after all required dependencies and certificates are healthy.
- [ ] Monitoring receives controlled test events and alerts reach named recipients.
- [ ] Pilot load-smoke passes on the actual target environment.

## Separate Windows x64 / WebView2 release gate

- [ ] Fresh install on real Windows x64 hardware.
- [ ] First launch and Foundation/Learner Agent flow.
- [ ] Spatial Practice boots in the intended WebView2/runtime path.
- [ ] Auto quality selection is recorded on at least Intel integrated, AMD integrated/APU and NVIDIA discrete GPU classes where available.
- [ ] Full offline use works where explicitly promised.
- [ ] Save, restart and data persistence.
- [ ] Export and backup.
- [ ] Upgrade and data migration.
- [ ] Restore.
- [ ] Uninstall/reinstall without unintended data loss.

Public or institutional pilot traffic should open only when mandatory target-environment items are evidenced. Linux GitHub Actions, a successful container build and the 208-test engineering matrix do not substitute for real-environment or Windows/WebView2 certification.
