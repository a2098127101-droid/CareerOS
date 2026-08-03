# CareerOS v1.2 Domain Model

## Canonical target entities

```text
Tenant / Organization
User / Profile
Experience
Evidence
Claim
Capability
Job
JobRequirement
Gap
Task
Artifact
ArtifactVersion
Review
Interview
KnowledgeDocument / KnowledgeChunk
Provider / Model / Route
Notification / AuditEvent
```

## Core relationship chain

```text
User
 -> Experience
 -> Evidence
 -> Claim
 -> Capability
 -> JobRequirement
 -> Gap
 -> Task
 -> Artifact
 -> Review
 -> Revision / ArtifactVersion
```

## v1.2 Showcase implementation

### Evidence
Each Evidence item has a stable ID and may carry explicit/inferred capability tags.

### Capability
Capability score/confidence are derived from current Evidence rather than fixed UI percentages.

### JobRequirement
Requirements are read from the selected structured job or derived fallback fields.

### Match / Gap
Each requirement is compared with Evidence/capability signals and categorized. Overall score is computed from current requirement coverage rather than a fixed percentage.

### Task
Tasks use a normalized schema with stable ID, priority, owner/due fields, status and origin metadata. Gap-generated tasks keep origin references to prevent duplicate open tasks.

### Artifact
Artifacts may reference Evidence IDs and maintain version information in local Showcase state.

## Backend normalization still required

The full relational graph should ultimately use dedicated persisted links such as:

```text
evidence_claim_links
evidence_capability_links
job_requirement_capability_links
artifact_claim_links
artifact_evidence_links
review_claim_links
review_evidence_links
task_origin_links
artifact_version_links
```

v1.2 does not claim all of these link tables are already canonical backend storage.
