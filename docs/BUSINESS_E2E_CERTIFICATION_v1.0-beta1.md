# Business E2E Certification · v1.0-beta1

## Purpose

Infrastructure probes cannot prove that CareerOS works as a product. `app/business_certification.py` and `scripts/certify_business_e2e.py` certify the real HTTP business path against the selected Repository backend.

## Required checks

### Semantic RAG quality

The certifier creates temporary tenant-scoped knowledge fixtures:

- current official source,
- outdated official source,
- current internal/non-authoritative source.

It requires:

- a real semantic embedding provider (`local_hash` is rejected),
- current-year source selection,
- authoritative source selection,
- certification-case `Recall@5 = 1`,
- no tenant-A source leakage into tenant-B search.

This is a deterministic release gate fixture, not a substitute for the larger product RAG benchmark dataset.

### Authenticated business flow

The certifier uses the running API and a participant session to execute:

1. create session;
2. Profile extraction;
3. Coach response;
4. private file upload;
5. Job Intelligence must distinguish a profile-supported requirement from an unsupported requirement without inferring capability from the job description;
6. Writer creates an artifact;
7. Reviewer produces structured review;
8. Evidence verification verifies artifact claims;
9. Critic/Revision creates a new artifact version;
10. Artifact trace is readable;
11. tenant-B attempts access to tenant-A session/workflow/evidence/evidence graph/feedback/artifact/versions/trace/file/job match and must receive 403/404;
12. model usage must contain successful live task records for `profile`, `coach`, `writer`, `reviewer`, `critic`, and `revision`.

A deterministic demo fallback cannot satisfy the usage proof.

## Certification identity safety

Each run creates unique `invalid.local` identities using cryptographically random passwords. Cleanup:

- deletes temporary sessions and knowledge fixtures,
- revokes operational session state through repository cleanup,
- de-identifies/archives created certification identities.

Cleanup errors cause `all_required_pass = false`.

## Certificate integrity

The business certificate:

- format: `careeros-business-certification-v1`;
- is HMAC-SHA256 signed with `APP_SECRET_KEY`;
- is bound to the deployment environment fingerprint;
- is freshness-limited by `BUSINESS_CERTIFICATION_MAX_AGE_HOURS`;
- is required by production `/ready`.

## Limitations

A PASS proves the tested flow in the certified environment. It does not by itself prove:

- 100/500/1000 concurrent AI capacity,
- every Provider/model combination,
- every browser,
- complete NLI-grade Evidence entailment,
- payment or SSO readiness.
