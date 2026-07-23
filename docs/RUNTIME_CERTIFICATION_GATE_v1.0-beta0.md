# Runtime Certification Gate · v1.0-beta0

## Certificate format

`careeros-runtime-certification-v2`

The report contains:

- certification profile;
- UTC generation time;
- deployment environment fingerprint;
- required/optional status for every check;
- evidence returned by each probe;
- `all_required_pass`;
- HMAC-SHA256 signature.

## Anti-copy protections

A certificate is invalid when:

- the signature is missing or modified;
- PostgreSQL/Redis/object-storage/embedding deployment coordinates change;
- the configured product/runtime target changes materially;
- `all_required_pass` is false;
- the certificate age exceeds `RUNTIME_CERTIFICATION_MAX_AGE_HOURS`.

Credentials themselves are not included in the fingerprint, so rotating a password/API secret for the same target does not expose secrets in the certificate.

## Profiles

### `full`
Requires PostgreSQL, pgvector, Redis, distributed limiter, Redis job round-trip, object storage round-trip, semantic embedding and LLM.

### `infrastructure`
Requires PostgreSQL, pgvector, Redis/distributed runtime, Redis job round-trip and object storage.

### `ai`
Requires real semantic embedding and LLM connectivity.

A skipped LLM test cannot make the `full` profile pass.

## Commands

```bash
python scripts/certify_runtime.py --profile full --storage-roundtrip
```

Verify via API:

```text
GET /api/admin/system/runtime-certification
GET /ready
GET /api/admin/system/readiness
```
