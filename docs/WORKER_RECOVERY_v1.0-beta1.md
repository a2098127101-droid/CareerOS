# Worker & Redis Recovery Certification · v1.0-beta1

## Independent worker proof

The certifier queues a `runtime_probe` job in the shared CareerOS Redis namespace and waits for completion. It never calls `work_once()` itself.

A PASS requires:

- `SUCCEEDED`,
- matching marker payload,
- `completed_by` populated,
- worker identity different from the certifier manager identity.

Therefore a separately running `scripts/run_worker.py` process/container is required.

## Lease recovery

Redis jobs track:

- `locked_by`,
- `heartbeat_at`,
- `lease_expires_at`,
- running sorted-set expiry,
- attempt count,
- dead-letter reason.

The recovery certification creates an expired RUNNING lease, calls `recover_stale()`, requires requeue, then requires an independent worker to finish the recovered job.

## Worker process decoupling

`scripts/run_worker.py` builds Settings, RepositoryContainer, EmbeddingGateway and BackgroundJobManager directly. It does not import FastAPI `app.main`.

API and worker share handlers through `app/job_handlers.py` to prevent duplicated job logic.

## Remaining limits

The current gate validates stale-lease recovery, but a future chaos suite should still cover:

- killing a real worker mid-handler,
- network partition,
- Redis restart,
- duplicate-delivery/idempotency behavior for long-running expensive handlers,
- dead-letter operational workflow,
- multiple simultaneous worker contention.
