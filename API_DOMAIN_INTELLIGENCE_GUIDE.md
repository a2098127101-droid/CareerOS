# Domain Intelligence API Guide

Base path: `/api/domain/v1`

## Recompute

```http
POST /api/domain/v1/recompute
Content-Type: application/json

{"job_id":"JOB-123","reason":"target job changed"}
```

The response includes claims, Claim–Evidence links, Claim–Capability links, Requirement mappings, Capability Assessments, Gaps and methodology explanation.

## Snapshot

```http
GET /api/domain/v1/snapshot?job_id=JOB-123
```

Returns current persisted domain state without silently creating a workspace.

## Explain a capability

```http
GET /api/domain/v1/capabilities/{capability_id}/explain
```

## Version history

```text
GET /claims/{claim_id}/versions
GET /capabilities/{capability_id}/versions
GET /requirements/{requirement_id}/versions
GET /gaps/{gap_id}/versions
```

## Optimistic locking

Claim and Gap updates accept `expected_version`. A stale request returns HTTP `409 version_conflict`.

## Subject scope

Advisor/Admin requests may specify `subject_user_id`; access is checked against tenant and advisor–participant class relationships.
