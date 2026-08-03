# CareerOS v1.4 Canonical Runtime Guide

## API mode
Use API mode when FastAPI is the authority. Browser storage is cache/offline UI state only.

### Canonical business paths
- Evidence: `/api/workspace/v1/evidence`
- Artifacts/versions: `/api/workspace/v1/artifacts`
- Tasks: `/api/workspace/v1/tasks`
- Real tenant users/invitations: `/api/workspace/v1/users`
- Knowledge: `/api/admin/knowledge/*`
- Jobs/matching: `/api/admin/jobs/*`, `/api/jobs/{job_id}/match`
- AI Coach: `/api/workspace/v1/ai/coach`
- Interview: `/api/workspace/v1/ai/interview/evaluate`
- PPT review: `/api/workspace/v1/ai/ppt/review`

### Generic runtime paths
`/api/runtime/v2/*` is for generic UI/runtime state and delta/revision synchronization. It is not the canonical store for Evidence/Artifact/Task/User/Knowledge/Job.

## Subject access
Staff must explicitly select a subject user. Advisor access requires a shared class membership. Do not use tenant-wide `owner=None` writes.

## Conflict handling
Send `expected_version` for mutable canonical entities. HTTP 409 means the client must reload/merge instead of overwrite.

## Local → API migration
The H5 migration helper only moves supported local Evidence/Artifact/Task drafts. Real identities, knowledge documents and job catalogs must use invitation/upload/CSV canonical flows.
