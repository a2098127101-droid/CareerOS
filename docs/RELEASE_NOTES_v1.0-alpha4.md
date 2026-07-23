# Release Notes — v1.0-alpha4 Runtime Infrastructure

This release focuses on runtime reliability rather than new UI surface area.

Key additions:

1. Redis-ready distributed rate limiting and runtime-state adapter.
2. Redis-ready background queue with worker entrypoint, progress, retry and cancellation.
3. Private local/S3-compatible file delivery with short-lived access.
4. Upload security policies and malware scanner hook.
5. SSE progressive status for Coach/Writer/Reviewer operations.
6. Structured logging, request IDs, metrics, liveness/readiness and Sentry/OTel foundation.
7. Stronger non-demo production fail-closed configuration.

The build remains `alpha` because live PostgreSQL/pgvector, Redis, S3 and model-provider E2E certification have not been completed in this environment.
