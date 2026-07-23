# Evidence Risk Governance · v1.0-alpha8

## Principle

Semantic relatedness is not proof. High-risk factual claims require explicit evidence and human accountability.

## High-risk signals

The current deterministic policy flags claims containing numbers or terms associated with:

- certificates / credentials;
- awards;
- degrees / education claims;
- income / salary / revenue;
- rankings;
- counts, percentages and other quantitative outcomes.

## Persisted fields

`evidence_claims` and `evidence_verification_history` now include:

- `risk_level`
- `requires_human_review`

Automated verification can still return `SUPPORTED` for an exact, explicitly evidenced high-risk fact, but the result remains marked for human review. A human override records a new history row rather than erasing the AI decision.

## Current limitation

This is not a complete NLI/entailment system. Complex causal, scope and capability claims still require a future NLI/LLM judge plus confidence calibration and human review policy.
