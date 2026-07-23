# API and Data Onboarding

## 1. LLM providers

Configure generation providers server-side. Never place real keys in browser code or the Showcase HTML.

Each Agent can have a primary and fallback model:

- Profile
- Coach
- Writer
- Reviewer
- Critic
- Revision

Before live use, verify connection, rate limits, model IDs, billing balance, latency and output format behavior.

## 2. Embedding provider

Generation and embedding are separate capabilities. Configure semantic embeddings independently:

```env
EMBEDDING_PROVIDER=openai_compatible
EMBEDDING_BASE_URL=https://provider.example/v1
EMBEDDING_API_KEY=...
EMBEDDING_MODEL=...
EMBEDDING_DIMENSIONS=...
```

Without a real semantic provider, CareerOS uses `local-hash-v1`, which is an offline deterministic fallback and must not be described as semantic embedding.

## 3. Knowledge ingestion

Recommended metadata:

- title
- category
- authority
- effective_year
- tenant_id
- scope
- priority
- tags

Suggested categories:

- policy_rule
- scoring_rule
- school_resource / organization_resource
- case
- course
- template
- internal

Cases are examples, not official rules.

## 4. Structured job data

Use CSV/API/ETL instead of PDF when data is naturally structured. Suggested fields:

- job_id
- title
- company
- industry
- city
- salary_min / salary_max
- education
- experience
- skills
- requirements
- source
- source_url
- published_at

A job requirement is not proof that a user possesses that capability.

## 5. User Evidence

Only user-provided or verified facts belong in the Evidence Ledger. Guidance, cases and external rules are separate sources.
