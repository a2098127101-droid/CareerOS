# Evidence Verification History · v1.0-alpha7

## Change

Claim verification now keeps durable decision history rather than overwriting the previous result.

Example:

```text
AI verifier
SUPPORTED · 0.91
        ↓
Advisor review
PARTIALLY_SUPPORTED · 0.78
Reason: claim scope is broader than the evidence
```

Both decisions remain queryable.

## APIs

```text
GET  /api/sessions/{session_id}/claims/{claim_id}/verification-history
POST /api/sessions/{session_id}/claims/{claim_id}/verify
```

Manual verification is restricted to authorized advisor/organization-admin roles and is written to the audit log.

## Current boundary

History and human override do not make the current verifier a formal NLI engine. True entailment/contradiction judging, confidence calibration and high-risk Claim human-review policy remain future work.
