from __future__ import annotations

import importlib.util
import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4


JOB_STATUSES = {"QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"}
JobHandler = Callable[[dict[str, Any], Callable[[int, str], None]], Any]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    job_id: str
    name: str
    tenant_id: str
    user_id: str = ""
    status: str = "QUEUED"
    progress: int = 0
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str = ""
    attempts: int = 0
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    idempotency_key: str = ""
    locked_by: str = ""
    heartbeat_at: str = ""
    lease_expires_at: str = ""
    timeout_seconds: int = 0
    retry_after: str = ""
    dead_letter_reason: str = ""
    completed_by: str = ""


class JobRuntimeError(RuntimeError):
    pass


class BackgroundJobManager:
    backend = "base"

    def __init__(self) -> None:
        self.handlers: dict[str, JobHandler] = {}

    def register(self, name: str, handler: JobHandler) -> None:
        self.handlers[name] = handler

    def enqueue(self, *, name: str, payload: dict[str, Any] | None, tenant_id: str, user_id: str = "", idempotency_key: str = "", timeout_seconds: int = 0) -> JobRecord:
        raise NotImplementedError

    def get(self, job_id: str, *, tenant_id: str) -> JobRecord | None:
        raise NotImplementedError

    def cancel(self, job_id: str, *, tenant_id: str) -> bool:
        raise NotImplementedError

    def retry(self, job_id: str, *, tenant_id: str) -> JobRecord | None:
        raise NotImplementedError

    def capabilities(self) -> dict[str, Any]:
        return {"backend": self.backend, "distributed": False, "ready": True}


class InProcessJobManager(BackgroundJobManager):
    """Development executor. Work survives HTTP request boundaries but not process restarts."""
    backend = "inprocess"

    def __init__(self, max_workers: int = 2, max_attempts: int = 3) -> None:
        super().__init__()
        self.executor = ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix="careeros-job")
        self.max_attempts = max(1, int(max_attempts))
        self._jobs: dict[str, JobRecord] = {}
        self._idempotency: dict[str, str] = {}
        self._lock = threading.Lock()

    def _save(self, job: JobRecord) -> None:
        job.updated_at = _now()
        with self._lock:
            self._jobs[job.job_id] = job

    def enqueue(self, *, name: str, payload: dict[str, Any] | None, tenant_id: str, user_id: str = "", idempotency_key: str = "", timeout_seconds: int = 0) -> JobRecord:
        if name not in self.handlers:
            raise JobRuntimeError(f"unknown background job: {name}")
        scoped_key = f"{tenant_id}:{name}:{idempotency_key}" if idempotency_key else ""
        with self._lock:
            if scoped_key and scoped_key in self._idempotency:
                existing = self._jobs.get(self._idempotency[scoped_key])
                if existing and existing.status != "CANCELLED":
                    return JobRecord(**asdict(existing))
            job = JobRecord(job_id=f"JOB-{uuid4().hex[:18].upper()}", name=name, tenant_id=tenant_id, user_id=user_id, payload=payload or {}, idempotency_key=idempotency_key, timeout_seconds=max(0, int(timeout_seconds)))
            self._jobs[job.job_id] = job
            if scoped_key:
                self._idempotency[scoped_key] = job.job_id
        self.executor.submit(self._execute, job.job_id)
        return JobRecord(**asdict(job))

    def _execute(self, job_id: str) -> None:
        job = self._jobs[job_id]
        if job.status == "CANCELLED":
            return
        job.status, job.attempts = "RUNNING", job.attempts + 1
        job.locked_by = "inprocess"
        job.heartbeat_at = _now()
        self._save(job)

        def progress(value: int, message: str = "") -> None:
            current = self._jobs.get(job_id)
            if not current or current.status == "CANCELLED":
                return
            current.progress = max(0, min(100, int(value)))
            current.message = message
            current.heartbeat_at = _now()
            self._save(current)

        try:
            result = self.handlers[job.name](dict(job.payload), progress)
            current = self._jobs[job_id]
            if current.status != "CANCELLED":
                current.status, current.progress, current.result = "SUCCEEDED", 100, result
                current.completed_by = "inprocess"
                current.locked_by = ""
                self._save(current)
        except Exception as exc:
            current = self._jobs[job_id]
            current.error = f"{type(exc).__name__}: {exc}"
            current.message = traceback.format_exc(limit=5)
            if current.attempts < self.max_attempts and current.status != "CANCELLED":
                current.status = "QUEUED"
                self._save(current)
                self.executor.submit(self._execute, job_id)
            else:
                current.status = "FAILED"
                current.dead_letter_reason = current.error
                current.locked_by = ""
                self._save(current)

    def get(self, job_id: str, *, tenant_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.tenant_id != tenant_id:
                return None
            return JobRecord(**asdict(job))

    def cancel(self, job_id: str, *, tenant_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.tenant_id != tenant_id or job.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return False
            job.status = "CANCELLED"
            job.updated_at = _now()
            return True

    def retry(self, job_id: str, *, tenant_id: str) -> JobRecord | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.tenant_id != tenant_id or job.status != "FAILED":
                return None
            job.status, job.error, job.message = "QUEUED", "", ""
            self._save(job)
        self.executor.submit(self._execute, job_id)
        return self.get(job_id, tenant_id=tenant_id)

    def capabilities(self) -> dict[str, Any]:
        return {"backend": self.backend, "distributed": False, "ready": True, "warning": "process-local development backend", "max_attempts": self.max_attempts}


class RedisJobManager(BackgroundJobManager):
    """Redis-backed durable queue/state. Execution is performed by scripts/run_worker.py."""
    backend = "redis"

    def __init__(self, redis_url: str, *, namespace: str = "careeros", ttl_seconds: int = 86400, max_attempts: int = 3) -> None:
        super().__init__()
        self.max_attempts = max(1, int(max_attempts))
        if not importlib.util.find_spec("redis"):
            raise JobRuntimeError("redis package is required for BACKGROUND_JOB_BACKEND=redis")
        import redis  # type: ignore
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.client.ping()
        self.namespace = namespace
        self.ttl_seconds = max(3600, int(ttl_seconds))
        self.worker_id = f"worker-{uuid4().hex[:10]}"
        self.lease_seconds = 120

    def _job_key(self, job_id: str) -> str:
        return f"{self.namespace}:job:{job_id}"

    def _idempotency_key(self, tenant_id: str, name: str, key: str) -> str:
        return f"{self.namespace}:job:idem:{tenant_id}:{name}:{key}"

    def _lease_key(self, job_id: str) -> str:
        return f"{self.namespace}:job:lease:{job_id}"

    def _recovery_key(self, job_id: str) -> str:
        return f"{self.namespace}:job:recovery:{job_id}"

    @property
    def dead_letter_key(self) -> str:
        return f"{self.namespace}:jobs:dead"

    @property
    def queue_key(self) -> str:
        return f"{self.namespace}:jobs:queue"

    @property
    def running_key(self) -> str:
        return f"{self.namespace}:jobs:running"

    def _save(self, job: JobRecord) -> None:
        job.updated_at = _now()
        key = self._job_key(job.job_id)
        self.client.set(key, json.dumps(asdict(job), ensure_ascii=False), ex=self.ttl_seconds)

    def _load_any(self, job_id: str) -> JobRecord | None:
        raw = self.client.get(self._job_key(job_id))
        if not raw:
            return None
        return JobRecord(**json.loads(raw))

    def enqueue(self, *, name: str, payload: dict[str, Any] | None, tenant_id: str, user_id: str = "", idempotency_key: str = "", timeout_seconds: int = 0) -> JobRecord:
        if name not in self.handlers:
            raise JobRuntimeError(f"unknown background job: {name}")
        job_id = f"JOB-{uuid4().hex[:18].upper()}"
        if idempotency_key:
            idem_key = self._idempotency_key(tenant_id, name, idempotency_key)
            if not self.client.set(idem_key, job_id, nx=True, ex=self.ttl_seconds):
                existing_id = self.client.get(idem_key)
                existing = self._load_any(existing_id) if existing_id else None
                if existing:
                    return existing
                self.client.set(idem_key, job_id, ex=self.ttl_seconds)
        job = JobRecord(job_id=job_id, name=name, tenant_id=tenant_id, user_id=user_id, payload=payload or {}, idempotency_key=idempotency_key, timeout_seconds=max(0, int(timeout_seconds)))
        self._save(job)
        self.client.lpush(self.queue_key, job.job_id)
        return job

    def get(self, job_id: str, *, tenant_id: str) -> JobRecord | None:
        job = self._load_any(job_id)
        return job if job and job.tenant_id == tenant_id else None

    def cancel(self, job_id: str, *, tenant_id: str) -> bool:
        job = self.get(job_id, tenant_id=tenant_id)
        if not job or job.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return False
        job.status = "CANCELLED"
        self._save(job)
        return True

    def work_once(self, timeout_seconds: int = 5) -> bool:
        item = self.client.brpop(self.queue_key, timeout=max(1, int(timeout_seconds)))
        if not item:
            return False
        _, job_id = item
        job = self._load_any(job_id)
        if not job or job.status == "CANCELLED":
            return True
        lease_key = self._lease_key(job_id)
        if not self.client.set(lease_key, self.worker_id, nx=True, ex=self.lease_seconds):
            self.client.lpush(self.queue_key, job_id)
            return True
        handler = self.handlers.get(job.name)
        if not handler:
            job.status, job.error = "FAILED", f"worker has no handler registered for {job.name}"
            job.dead_letter_reason = job.error
            self._save(job)
            self.client.lpush(self.dead_letter_key, job_id)
            self.client.delete(lease_key)
            return True
        job.status, job.attempts = "RUNNING", job.attempts + 1
        job.locked_by = self.worker_id
        job.heartbeat_at = _now()
        lease_deadline = time.time() + self.lease_seconds
        job.lease_expires_at = datetime.fromtimestamp(lease_deadline, timezone.utc).isoformat()
        self._save(job)
        self.client.zadd(self.running_key, {job_id: lease_deadline})

        heartbeat_stop = threading.Event()

        def heartbeat_loop() -> None:
            interval = max(1.0, self.lease_seconds / 3)
            while not heartbeat_stop.wait(interval):
                current = self._load_any(job_id)
                if not current or current.status != "RUNNING":
                    return
                deadline = time.time() + self.lease_seconds
                current.heartbeat_at = _now()
                current.lease_expires_at = datetime.fromtimestamp(deadline, timezone.utc).isoformat()
                self.client.expire(lease_key, self.lease_seconds)
                self.client.zadd(self.running_key, {job_id: deadline})
                self._save(current)

        heartbeat_thread = threading.Thread(target=heartbeat_loop, name=f"careeros-heartbeat-{job_id[-6:]}", daemon=True)
        heartbeat_thread.start()

        def progress(value: int, message: str = "") -> None:
            current = self._load_any(job_id)
            if not current or current.status == "CANCELLED":
                return
            current.progress = max(0, min(100, int(value)))
            current.message = message
            deadline = time.time() + self.lease_seconds
            current.heartbeat_at = _now()
            current.lease_expires_at = datetime.fromtimestamp(deadline, timezone.utc).isoformat()
            self.client.expire(lease_key, self.lease_seconds)
            self.client.zadd(self.running_key, {job_id: deadline})
            self._save(current)

        try:
            result = handler(dict(job.payload), progress)
            current = self._load_any(job_id) or job
            if current.status != "CANCELLED":
                current.status, current.progress, current.result = "SUCCEEDED", 100, result
                current.completed_by = self.worker_id
                current.locked_by = ""
                current.lease_expires_at = ""
                self._save(current)
        except Exception as exc:
            current = self._load_any(job_id) or job
            current.error = f"{type(exc).__name__}: {exc}"
            current.message = traceback.format_exc(limit=5)
            if current.attempts < self.max_attempts and current.status != "CANCELLED":
                current.status = "QUEUED"
                current.locked_by = ""
                current.lease_expires_at = ""
                self._save(current)
                self.client.lpush(self.queue_key, job_id)
            else:
                current.status = "FAILED"
                current.dead_letter_reason = current.error
                current.locked_by = ""
                current.lease_expires_at = ""
                self._save(current)
                self.client.lpush(self.dead_letter_key, job_id)
        finally:
            heartbeat_stop.set()
            self.client.delete(lease_key)
            self.client.zrem(self.running_key, job_id)
        return True

    def recover_stale(self, *, limit: int = 100) -> dict[str, int]:
        """Requeue RUNNING jobs whose worker lease expired.

        Every worker may call this method. A short per-job Redis recovery lock prevents two workers
        that observed the same expired sorted-set entry from both requeueing the same job.
        """
        now = time.time()
        recovered = failed = skipped = 0
        for job_id in self.client.zrangebyscore(self.running_key, 0, now, start=0, num=max(1, int(limit))):
            recovery_key = self._recovery_key(job_id)
            if not self.client.set(recovery_key, self.worker_id, nx=True, ex=max(5, self.lease_seconds)):
                skipped += 1
                continue
            try:
                lease_key = self._lease_key(job_id)
                if self.client.exists(lease_key):
                    skipped += 1
                    continue
                job = self._load_any(job_id)
                self.client.zrem(self.running_key, job_id)
                if not job or job.status != "RUNNING":
                    skipped += 1
                    continue
                job.locked_by = ""
                job.lease_expires_at = ""
                job.message = "recovered after expired worker lease"
                if job.attempts < self.max_attempts:
                    job.status = "QUEUED"
                    self._save(job)
                    self.client.lpush(self.queue_key, job_id)
                    recovered += 1
                else:
                    job.status = "FAILED"
                    job.dead_letter_reason = "worker lease expired after maximum attempts"
                    self._save(job)
                    self.client.lpush(self.dead_letter_key, job_id)
                    failed += 1
            finally:
                # Removing this lock is safe because the running-set entry/status has already been updated.
                # A contender that held a stale local copy will observe non-RUNNING state and skip.
                self.client.delete(recovery_key)
        return {"recovered": recovered, "failed": failed, "skipped": skipped}

    def retry(self, job_id: str, *, tenant_id: str) -> JobRecord | None:
        job = self.get(job_id, tenant_id=tenant_id)
        if not job or job.status != "FAILED":
            return None
        job.status, job.error, job.message = "QUEUED", "", ""
        self._save(job)
        self.client.lpush(self.queue_key, job_id)
        return job

    def capabilities(self) -> dict[str, Any]:
        try:
            ok = bool(self.client.ping())
            return {"backend": self.backend, "distributed": True, "ready": ok, "queue_depth": int(self.client.llen(self.queue_key)), "dead_letter_depth": int(self.client.llen(self.dead_letter_key)), "running_depth": int(self.client.zcard(self.running_key)), "max_attempts": self.max_attempts, "lease_seconds": self.lease_seconds}
        except Exception as exc:
            return {"backend": self.backend, "distributed": True, "ready": False, "error": str(exc)}


def build_job_manager(*, backend: str, redis_url: str, max_workers: int = 2, ttl_seconds: int = 86400, max_attempts: int = 3) -> BackgroundJobManager:
    name = (backend or "inprocess").strip().lower()
    if name == "redis":
        if not redis_url:
            raise JobRuntimeError("REDIS_URL is required when BACKGROUND_JOB_BACKEND=redis")
        return RedisJobManager(redis_url, ttl_seconds=ttl_seconds, max_attempts=max_attempts)
    if name != "inprocess":
        raise JobRuntimeError(f"unsupported background job backend: {name}")
    return InProcessJobManager(max_workers=max_workers, max_attempts=max_attempts)
