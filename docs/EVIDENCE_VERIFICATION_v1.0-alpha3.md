# Evidence Verification — v1.0-alpha3

## Objective

Traceability answers:

> Which evidence is linked to this claim?

Verification adds a harder question:

> Does that evidence actually support the claim?

Alpha3 introduces a conservative verification foundation. It does not yet claim full legal/scientific entailment proof.

## Verification states

- `SUPPORTED`
- `PARTIALLY_SUPPORTED`
- `CONTRADICTED`
- `UNSUPPORTED`
- `UNVERIFIED`

## Inputs

For each artifact claim:

1. candidate Evidence items are collected within the authorized tenant/session scope;
2. lexical and numeric consistency signals are calculated;
3. negation mismatch is checked;
4. semantic similarity is used only when a real semantic embedding provider succeeds.

`local_hash` is never treated as semantic evidence.

## Conservative behavior

Examples:

- Claim contains a number absent from or inconsistent with all evidence → generally UNSUPPORTED/PARTIAL/CONTRADICTED depending on evidence.
- Claim and evidence have opposing negation meaning → CONTRADICTED candidate.
- Weak/ambiguous relationship → UNVERIFIED rather than forced SUPPORTED.
- No evidence → UNSUPPORTED.

## Persistence

Claims now persist:

- verification_status
- verification_confidence
- verified_by
- verified_at

API:

```text
POST /api/sessions/{session_id}/evidence-verify
```

Optional body:

```json
{"claim_ids":["CLM-..."]}
```

If omitted, eligible artifact claims in the session can be verified.

## Current limitation

Alpha3 is a deterministic/semantic-assisted verifier, not a complete NLI system. The next stage should support a second-stage entailment adapter:

```text
Deterministic checks
    ↓
Candidate evidence
    ↓
Semantic retrieval
    ↓
Optional NLI / LLM judge
    ↓
Human confirmation for high-risk claims
```

High-risk numerical, credential, award, income, headcount and outcome claims should remain evidence-required and human-reviewable.
