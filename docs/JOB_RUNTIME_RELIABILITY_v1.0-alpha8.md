# Background Job Reliability · v1.0-alpha8

## Idempotency

`enqueue()` accepts an optional `idempotency_key`. The effective key is tenant + job type + key, preventing cross-tenant collisions.

For in-process development runtime, equivalent active submissions return the same Job ID. Redis runtime uses a dedicated idempotency key with TTL.

## Lease / heartbeat foundation

Redis workers acquire a per-job lease before execution. Progress updates refresh the lease TTL and heartbeat timestamp. Failed terminal jobs record a dead-letter reason and are pushed to a dead-letter list.

This reduces duplicate execution risk but does not yet claim a fully certified distributed exactly-once system. Real Redis worker crash/recovery and lease-expiry behavior still requires multi-worker staging certification.

## Current async use

Knowledge reindex uses a tenant-scoped idempotency key for `missing-only` versus `full` rebuild requests.
