# RAG Retrieval Evaluation v1.5.1

## Contract

CareerOS now composes:

1. query term normalization;
2. portable Okapi BM25;
3. SQLite FTS5 BM25 when available;
4. semantic vector score from the configured Embedding provider;
5. metadata, authority and effective-year controls;
6. optional server-side remote Reranker;
7. evidence/citation output.

Remote Reranker adapters are available for Cohere, Jina, Voyage and compatible
HTTP contracts. API keys remain server-side.

## Checked-in fixture

`data_samples/rag_eval_v1` is explicitly **Demo Data** and contains three
deterministic cases. It protects ranking, citation, authority and year-filter
contracts in CI. It does not establish production relevance quality.

Local result on 2026-07-27:

| Metric | Result |
|---|---:|
| Recall@5 | 1.0 |
| Recall@10 | 1.0 |
| MRR@10 | 1.0 |
| Citation source accuracy | 1.0 |
| Authority accuracy | 1.0 |
| Effective-year accuracy | 1.0 |
| Required-term coverage | 1.0 |

## Remaining evaluation gate

Before production claims, add a versioned corpus with at least:

- real authorized rules/resources;
- current-year and stale-year conflicts;
- hard negatives;
- Chinese paraphrases and multilingual queries;
- adjudicated relevance labels;
- provider/model/version metadata;
- BM25-only, vector-only, hybrid and reranked ablations.

No live semantic Embedding or remote Reranker was called in this test run because
no credentials were available.
