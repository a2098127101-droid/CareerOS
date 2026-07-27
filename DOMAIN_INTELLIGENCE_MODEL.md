# CareerOS v1.5 Domain Intelligence Model

## Claim

A versioned, attributable assertion extracted from Evidence, an Artifact Version or an authorized manual entry.

Key fields: `claim_id`, `source_type`, `source_id`, `source_locator`, `claim_text`, `claim_type`, `version`, `owner_user_id`.

## Capability

A stable definition in a versioned taxonomy. Global baseline capabilities can be overridden or extended with tenant-scoped capabilities.

A Capability Assessment is separate from the Capability definition and stores:

- potential score;
- verified score;
- confidence;
- methodology version;
- contribution rows;
- assessment version.

## Requirement

A canonical job requirement generated or imported by Job Intelligence. v1.5 stores versioned snapshots in `job_requirement_versions` and maps each requirement to one or more capabilities with weight and minimum score.

## Gap

A versioned comparison between a Requirement and the current Capability Assessment.

Gap types:

- `NO_CAPABILITY`
- `LOW_CAPABILITY`
- `NO_VERIFIED_EVIDENCE`
- `PARTIAL_EVIDENCE`
- `COVERED`

Lifecycle states:

- `open`
- `planned`
- `in_progress`
- `resolved`
- `accepted`
- `dismissed`

## Explainability

A capability explanation returns:

```text
Capability Definition
  → Latest Assessment and methodology
  → Contributing Claims
  → Claim–Capability relation
  → Claim–Evidence relations
  → Evidence trust state and confidence
```

## Auditability

`domain_audit_events` records entity, action, actor, subject, before/after state, reason, correlation identifier and time. Historical values are retained in dedicated version tables rather than reconstructed from logs alone.
