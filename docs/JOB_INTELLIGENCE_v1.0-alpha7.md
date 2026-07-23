# Job Intelligence · v1.0-alpha7

## Purpose

Structured job data and participant capability evidence are evaluated independently.

```text
Job → Requirement decomposition
Participant → Profile + Evidence
              ↓
          Match Engine
              ↓
MATCHED / PARTIAL / MISSING / UNKNOWN
```

## APIs

```text
GET  /api/admin/jobs/{job_id}/requirements
POST /api/jobs/{job_id}/match
```

Match request:

```json
{"session_id": "..."}
```

Each requirement returns:

- requirement
- category
- importance
- status
- evidence
- reason
- confidence
- recommended_action

## Non-inference rule

A requirement present in a job description never becomes a participant capability unless participant-side Evidence supports it.

## Current boundary

Alpha7 uses deterministic decomposition/matching heuristics. A standardized occupation/skill taxonomy, semantic requirement normalization, external job API ETL/deduplication, and model-assisted decomposition with evaluation are not yet complete.
