# Redis & Background Jobs — v1.0-alpha4

## Development

```env
RUNTIME_STATE_BACKEND=memory
BACKGROUND_JOB_BACKEND=inprocess
```

This mode is process-local and must not be treated as horizontally scalable.

## Production target

```env
RUNTIME_STATE_BACKEND=redis
REDIS_URL=redis://redis:6379/0
BACKGROUND_JOB_BACKEND=redis
BACKGROUND_JOB_MAX_ATTEMPTS=3
```

Run a separate worker:

```bash
python scripts/run_worker.py
```

## Job semantics

Jobs carry:

- job_id;
- tenant_id;
- user_id;
- status;
- progress;
- message;
- attempts;
- result/error;
- timestamps.

Tenant checks are enforced when job state is retrieved or mutated. Participant users cannot read another user's owned job merely because they share a tenant.

## Current built-in job

`knowledge_reindex` supports tenant-scoped reindexing. More named handlers should be added for document parsing, embedding, batch review, job ETL and export.

## Boundary

The Redis implementation is coded but not live-verified in this build environment because no Redis service/package was available in the original runtime image. Installation/runtime dependencies are declared for deployment.
