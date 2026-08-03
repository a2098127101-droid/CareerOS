# CareerOS Pilot Go-Live Checklist

Use this checklist for the first controlled university pilot. A checked box must point to verifiable evidence: a configuration review, test report, signed certification, backup artifact or named owner.

## 1. Release integrity

- [ ] Deploy a reviewed commit or release tag, not a working branch.
- [ ] CI test matrix passes at the expected locked count.
- [ ] Dependency, secret, filesystem and container scans pass.
- [ ] Production Compose configuration validates without warnings that alter intended behavior.
- [ ] Release ZIP checksum matches the attached SHA-256 file.
- [ ] Release manifest contains no runtime database, real student data, secrets, logs or certification files.

## 2. Domain and TLS

- [ ] `DOMAIN` resolves to the production server.
- [ ] `STORAGE_DOMAIN` resolves to the production server.
- [ ] ACME contact email is monitored.
- [ ] HTTPS certificate is valid for both hosts.
- [ ] HTTP redirects to HTTPS.
- [ ] HSTS and security headers are present.

## 3. Identity and access

- [ ] `DEMO_MODE=false`.
- [ ] `AUTH_REQUIRED=true`.
- [ ] Self-registration is disabled unless institutionally approved.
- [ ] Bootstrap administrator password has been rotated after first login.
- [ ] Student, advisor, organization administrator and platform administrator permissions are tested separately.
- [ ] Cross-tenant object IDs return non-disclosing 404/403 responses.
- [ ] Terminated or archived users cannot reuse active sessions.

## 4. Data infrastructure

- [ ] PostgreSQL is the active repository backend.
- [ ] Alembic is at the reviewed head revision.
- [ ] Application connection uses a non-owner, non-superuser, `NOBYPASSRLS` role.
- [ ] PostgreSQL role and repository certification passes against the application connection.
- [ ] Redis authentication and persistence are enabled.
- [ ] Independent worker execution and recovery are verified.
- [ ] MinIO/S3 bucket is private.
- [ ] Presigned object retrieval works through the public storage endpoint.
- [ ] PostgreSQL, Redis and MinIO API ports are not publicly exposed.

## 5. AI and retrieval

- [ ] At least one generation provider is configured and tested.
- [ ] Primary and fallback routes are configured for required tasks.
- [ ] A real semantic embedding provider is configured.
- [ ] Retrieval evaluation passes using institution-appropriate material.
- [ ] Model capability records include current input/output pricing or are explicitly unpriced.
- [ ] PII redaction and third-party model data minimization are enabled.
- [ ] Prompt and trace retention settings match the privacy notice.
- [ ] AI output is labelled as decision support, not employment prediction.

## 6. Student business flow

Test with a non-administrator student account:

- [ ] Login redirects to the project workspace.
- [ ] A project can be created from a published immutable template version.
- [ ] Required answers persist after refresh.
- [ ] The next-action card changes when project requirements are complete.
- [ ] Evidence files upload, scan, store and retrieve correctly.
- [ ] The first artifact is generated from the correct project session.
- [ ] Review produces a score and prioritized issues.
- [ ] Revision creates a new artifact version rather than overwriting history.
- [ ] Exported content is readable and accurately labelled.
- [ ] The project can be completed only after the permitted status transition.

## 7. Advisor business flow

Test with an advisor assigned to a real pilot group:

- [ ] Advisor sees only assigned groups and sessions.
- [ ] Intervention queue prioritizes review, revision and stalled projects.
- [ ] Student evidence and artifact counts are visible in the authorized inspector.
- [ ] Internal notes persist without being exposed to the student.
- [ ] Student-facing feedback creates the expected task.
- [ ] Follow-up tasks can be created and completed.

## 8. Governance

- [ ] Organization administrators can open the AI cost and audit center.
- [ ] Advisors and students cannot open organization governance APIs.
- [ ] Calls, tokens, latency, errors and model identity are recorded.
- [ ] Unknown model prices appear as unpriced calls, not zero-cost calls.
- [ ] Project creation, answer updates, milestone changes and governance access are audited.
- [ ] Audit retention and access rules are documented.

## 9. Privacy and institutional operations

- [ ] Institution-approved privacy notice and consent wording are published.
- [ ] Data retention periods are configured and documented.
- [ ] Export and deletion-request workflows have named human owners.
- [ ] No real student data is present in demo or test tenants.
- [ ] Uploaded malware-scanning policy is configured or the residual risk is formally accepted.
- [ ] Support contact, incident owner and escalation route are published.

## 10. Backup, restore and rollback

- [ ] Encrypted off-server PostgreSQL backup completes successfully.
- [ ] Backup checksum verifies.
- [ ] Restore has been tested in an isolated environment.
- [ ] Previous release image/tag remains available.
- [ ] Database migration rollback/forward-fix plan is documented.
- [ ] Traffic can be stopped without deleting persistent volumes.

## 11. Observability and capacity

- [ ] Error monitoring receives a controlled test error.
- [ ] API latency, 5xx rate, queue depth, failed jobs and storage capacity are monitored.
- [ ] Alerts have named recipients and escalation thresholds.
- [ ] Pilot concurrency/load smoke test passes against the target server.
- [ ] Disk, database and object-storage growth thresholds are defined.

## Go / No-Go decision

Release only when:

1. `/live` returns HTTP 200;
2. `/ready` returns HTTP 200;
3. PostgreSQL, runtime and business certifications are valid and current;
4. no unresolved critical/high security finding remains;
5. the student and advisor business flows above pass on the target environment;
6. an accountable release owner records the deployment commit, date and residual risks.

Starting containers alone is not a production-readiness result.
