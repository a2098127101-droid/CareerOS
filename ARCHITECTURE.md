# CareerOS v1.5 Architecture

## 1. Runtime path

```text
Unified UI
  → Feature Service / DataAdapter
  → FastAPI BFF
  → Canonical Domain Services
      ├ Evidence Store / Verification
      ├ Artifact Version Store
      ├ Job Intelligence
      └ DomainIntelligenceService
  → Repository Interface
      ├ SQLite local compatibility
      └ SQLAlchemy/PostgreSQL
```

Generic Runtime remains limited to UI/runtime state. Claim, Capability Assessment, Requirement Mapping and Gap are canonical server-side business entities.

## 2. Domain path

```text
Evidence / Artifact Version
  → Claim
  → Claim–Evidence Verification Link
  → Claim–Capability Link
  → Capability Assessment Version

Job
  → Job Requirement
  → Requirement Version
  → Requirement–Capability Mapping

Assessment + Requirement
  → Gap
  → Gap Version / Status / Audit
```

## 3. Source of truth

| Object | Source of truth |
|---|---|
| Evidence | Evidence Store |
| Artifact and version | Artifact Store |
| Job and requirement | Job Store |
| Claim | `domain_claims` |
| Capability definition | `capabilities` |
| Capability result | `capability_assessments` |
| Requirement mapping | `job_requirement_capability_links` |
| Gap | `career_gaps` |
| Domain history | version tables + `domain_audit_events` |

## 4. Consistency model

- Claim and Gap mutations support expected-version conflict checks.
- Assessment recomputation always creates a new assessment version.
- Requirement snapshots are deduplicated; changed snapshots increment the requirement version.
- Audit records store actor, subject, before/after, reason and timestamp.
- Evidence edits invalidate prior trust decisions when substantive content changes.

## 5. Scoring boundary

The v1.5 methodology is deterministic and transparent. It separates:

- **Potential score:** may include self-reported/candidate support.
- **Verified score:** weighted only by trusted Evidence states and verified/partial support.

It is not a psychometric or causal model.
