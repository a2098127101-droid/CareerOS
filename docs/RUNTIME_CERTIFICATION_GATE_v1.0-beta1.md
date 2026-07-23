# Runtime Certification Gate · v1.0-beta1

## Runtime certificate required checks

Full profile requires PASS for:

- PostgreSQL live connection/schema + Repository certificate,
- pgvector extension/vector column,
- Redis,
- distributed rate-limit shared state,
- independent Redis background-job completion,
- expired-worker-lease recovery,
- S3-compatible private-object SDK + presigned HTTP round-trip,
- real semantic embedding provider call,
- at least one enabled real LLM Provider connectivity test,
- configured external observability sink health endpoint.

Configuration alone never becomes PASS.

## Certificate security

Runtime certificates are:

- HMAC-SHA256 signed,
- bound to database/Redis/storage/embedding deployment coordinates,
- freshness-limited,
- rejected after tampering, environment movement or expiry.

## Production readiness

Production `/ready` requires:

1. a valid current runtime certificate; and
2. a valid current Business E2E certificate.

Missing, stale, invalid or incomplete certificates result in a readiness blocker.

## Observability limitation

The beta1 observability check validates that a configured external observability/collector health endpoint responds successfully. It does **not yet prove end-to-end ingestion of a Sentry event or OpenTelemetry span**. That remains a hardening item for the final production gate.

## S3 public/internal endpoint split

For self-hosted MinIO or private S3-compatible networks, configure:

```text
S3_ENDPOINT                  internal SDK endpoint
S3_PUBLIC_ENDPOINT           browser-facing endpoint used to sign URLs
S3_CERTIFICATION_FETCH_ENDPOINT internal certifier transport endpoint
```

The certifier can transport the signed request over the internal endpoint while preserving the public `Host` header, so SigV4 validation still tests the browser-facing signed host.
