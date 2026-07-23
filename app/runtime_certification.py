from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

from .core.database import create_database_engine, postgres_driver_available, schema_health
from .core.postgres_certification import load_certification
from .embedding_gateway import EmbeddingGateway
from .pgvector_backend import pgvector_capabilities
from .runtime_state import RedisRateLimiter, redis_capabilities
from .background_jobs import JobRecord, RedisJobManager
from .storage import StorageError


@dataclass
class CheckResult:
    name: str
    status: str  # PASS | FAIL | NOT_CONFIGURED | NOT_VERIFIED
    detail: str
    evidence: dict[str, Any]
    required: bool = True


def _endpoint_identity(raw_url: str, default_port: int = 0) -> str:
    raw = (raw_url or "").strip()
    if not raw:
        return ""
    normalized = raw.replace("postgresql+psycopg://", "postgresql://", 1).replace("postgres://", "postgresql://", 1)
    parsed = urlparse(normalized)
    port = parsed.port or default_port
    return f"{parsed.scheme}|{parsed.hostname or ''}|{port}|{parsed.path.lstrip('/')}"


def runtime_environment_fingerprint(settings) -> str:
    """Bind a runtime certificate to non-secret deployment coordinates.

    Credentials are deliberately excluded. Moving the certificate to another database/Redis/bucket/
    embedding target invalidates it, while credential rotation for the same target does not.
    """
    payload = {
        "app_env": getattr(settings, "app_env", "development"),
        "repository_backend": getattr(settings, "repository_backend", "sqlite"),
        "database": _endpoint_identity(getattr(settings, "database_url", ""), 5432),
        "redis": _endpoint_identity(getattr(settings, "redis_url", ""), 6379),
        "storage_provider": getattr(settings, "storage_provider", "local"),
        "s3_endpoint": getattr(settings, "s3_endpoint", ""),
        "s3_public_endpoint": getattr(settings, "s3_public_endpoint", ""),
        "s3_bucket": getattr(settings, "s3_bucket", ""),
        "embedding_provider": getattr(settings, "embedding_provider", "local_hash"),
        "embedding_base_url": getattr(settings, "embedding_base_url", ""),
        "embedding_model": getattr(settings, "embedding_model", "local-hash-v1"),
        "product_preset": getattr(settings, "product_preset", "career_development"),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _signature_payload(report: dict[str, Any]) -> bytes:
    clean = {k: v for k, v in report.items() if k != "signature"}
    return json.dumps(clean, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_runtime_certification(report: dict[str, Any], secret_key: str) -> dict[str, Any]:
    signed = dict(report)
    signed["signature"] = hmac.new(secret_key.encode("utf-8"), _signature_payload(signed), hashlib.sha256).hexdigest()
    return signed


def load_runtime_certification(path: str | Path, *, settings) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {"valid": False, "reason": "runtime certification file not found", "path": str(target)}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"valid": False, "reason": f"invalid runtime certification file: {exc}", "path": str(target)}

    reasons: list[str] = []
    if data.get("format") != "careeros-runtime-certification-v2":
        reasons.append("unsupported runtime certification format")
    if data.get("environment_fingerprint") != runtime_environment_fingerprint(settings):
        reasons.append("runtime certification belongs to a different deployment configuration")
    signature = str(data.get("signature") or "")
    expected = hmac.new(settings.app_secret_key.encode("utf-8"), _signature_payload(data), hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        reasons.append("runtime certification signature is missing or invalid")
    if not data.get("all_required_pass"):
        reasons.append("one or more required runtime checks did not pass")

    generated_at = data.get("generated_at")
    try:
        generated = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - generated.astimezone(timezone.utc)).total_seconds() / 3600
        if age_hours > max(1, int(settings.runtime_certification_max_age_hours)):
            reasons.append(f"runtime certification is stale ({age_hours:.1f}h old)")
    except Exception:
        reasons.append("runtime certification generated_at is invalid")

    return {**data, "valid": not reasons, "reason": "; ".join(reasons), "path": str(target)}


class RuntimeCertification:
    """Live deployment certification orchestrator.

    PASS is awarded only after a real interaction with the target dependency. Configuration alone
    never becomes PASS. The full profile intentionally checks distributed behavior, not only pings.
    """

    def __init__(self, *, settings, embedding_gateway: EmbeddingGateway, object_storage, model_store=None, llm_gateway=None):
        self.settings = settings
        self.embedding_gateway = embedding_gateway
        self.object_storage = object_storage
        self.model_store = model_store
        self.llm_gateway = llm_gateway

    def check_postgres(self) -> CheckResult:
        if not self.settings.database_url:
            return CheckResult("postgresql", "NOT_CONFIGURED", "DATABASE_URL is not configured", {})
        if not postgres_driver_available():
            return CheckResult("postgresql", "NOT_VERIFIED", "PostgreSQL driver is not installed in this runtime", {"driver_available": False})
        cert = load_certification(self.settings.postgres_certification_file, database_url=self.settings.database_url)
        try:
            started = time.perf_counter()
            engine = create_database_engine(self.settings.database_url, self.settings.db_path)
            health = schema_health(engine)
            with engine.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            engine.dispose()
        except Exception as exc:
            return CheckResult("postgresql", "FAIL", f"live PostgreSQL connection/schema probe failed: {exc}", {"certification_valid": bool(cert.get("valid"))})
        if not health.get("ready"):
            return CheckResult("postgresql", "FAIL", "live PostgreSQL schema is incomplete", {"missing": health.get("missing", [])[:20], "latency_ms": latency_ms})
        if not cert.get("valid"):
            return CheckResult("postgresql", "NOT_VERIFIED", cert.get("reason") or "repository certification missing/stale", {"schema_ready": True, "latency_ms": latency_ms, "certification_valid": False})
        return CheckResult("postgresql", "PASS", "live PostgreSQL connection, schema and repository certification verified", {"certified_at": cert.get("certified_at"), "schema_ready": True, "latency_ms": latency_ms, "certification_valid": True})

    def check_pgvector(self) -> CheckResult:
        if not self.settings.database_url:
            return CheckResult("pgvector", "NOT_CONFIGURED", "DATABASE_URL is not configured", {})
        if not postgres_driver_available():
            return CheckResult("pgvector", "NOT_VERIFIED", "PostgreSQL driver is not installed in this runtime", {"driver_available": False})
        try:
            engine = create_database_engine(self.settings.database_url, self.settings.db_path)
            caps = pgvector_capabilities(engine)
            engine.dispose()
            return CheckResult("pgvector", "PASS" if caps.get("ready") else "FAIL", "pgvector extension and vector column verified" if caps.get("ready") else "pgvector extension/vector column is not ready", caps)
        except Exception as exc:
            return CheckResult("pgvector", "FAIL", str(exc), {})

    def check_redis(self) -> CheckResult:
        if not self.settings.redis_url:
            return CheckResult("redis", "NOT_CONFIGURED", "REDIS_URL is not configured", {})
        caps = redis_capabilities(self.settings.redis_url)
        return CheckResult("redis", "PASS" if caps.get("ready") else "FAIL", caps.get("error") or "redis ping succeeded", caps)

    def check_distributed_rate_limit(self) -> CheckResult:
        if not self.settings.redis_url:
            return CheckResult("distributed_rate_limit", "NOT_CONFIGURED", "REDIS_URL is not configured", {})
        namespace = f"careeros-cert-{uuid4().hex[:10]}"
        try:
            limiter_a = RedisRateLimiter(self.settings.redis_url, namespace=namespace)
            limiter_b = RedisRateLimiter(self.settings.redis_url, namespace=namespace)
            first = limiter_a.allow(scope="cert", key="shared", limit=1, window_seconds=5)
            second = limiter_b.allow(scope="cert", key="shared", limit=1, window_seconds=5)
            ok = first is True and second is False
            return CheckResult("distributed_rate_limit", "PASS" if ok else "FAIL", "two independent Redis clients shared one atomic rate-limit state" if ok else "distributed limiter did not enforce shared state", {"first_allowed": first, "second_allowed": second})
        except Exception as exc:
            return CheckResult("distributed_rate_limit", "FAIL", str(exc), {})

    def check_background_jobs(self) -> CheckResult:
        """Verify API/certifier -> Redis -> *independent worker* -> Redis state.

        The certifier deliberately never calls ``work_once``. A PASS therefore requires a separately
        running worker process/container registered with the shared ``runtime_probe`` handler.
        """
        if not self.settings.redis_url:
            return CheckResult("redis_background_jobs", "NOT_CONFIGURED", "REDIS_URL is not configured", {})
        marker = uuid4().hex
        try:
            manager = RedisJobManager(self.settings.redis_url, namespace="careeros", ttl_seconds=3600, max_attempts=1)
            # enqueue() validates handler registration locally, but execution must happen in the independent worker.
            manager.register("runtime_probe", lambda payload, progress: {"marker": payload["marker"]})
            job = manager.enqueue(
                name="runtime_probe", payload={"marker": marker}, tenant_id="runtime-certification",
                idempotency_key=f"runtime-cert:{marker}", timeout_seconds=30,
            )
            deadline = time.time() + 30
            finished = None
            while time.time() < deadline:
                finished = manager.get(job.job_id, tenant_id="runtime-certification")
                if finished and finished.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                    break
                time.sleep(0.5)
            ok = bool(
                finished and finished.status == "SUCCEEDED"
                and (finished.result or {}).get("marker") == marker
                and finished.completed_by and finished.completed_by != manager.worker_id
            )
            evidence = {
                "job_id": job.job_id,
                "status": getattr(finished, "status", None),
                "executed_by": getattr(finished, "completed_by", "") if finished else "",
                "certifier_worker_id": manager.worker_id,
                "independent_worker": bool(finished and finished.completed_by and finished.completed_by != manager.worker_id),
            }
            return CheckResult(
                "redis_background_jobs", "PASS" if ok else "FAIL",
                "independent Redis worker process completed the certification job" if ok else
                "independent worker did not complete the certification job within 30 seconds",
                evidence,
            )
        except Exception as exc:
            return CheckResult("redis_background_jobs", "FAIL", str(exc), {})

    def check_worker_crash_recovery(self) -> CheckResult:
        """Simulate a worker crash by creating an expired RUNNING lease, then require recovery + external execution."""
        if not self.settings.redis_url:
            return CheckResult("worker_crash_recovery", "NOT_CONFIGURED", "REDIS_URL is not configured", {})
        marker = uuid4().hex
        try:
            manager = RedisJobManager(self.settings.redis_url, namespace="careeros", ttl_seconds=3600, max_attempts=3)
            manager.register("runtime_probe", lambda payload, progress: {"marker": payload["marker"]})
            job = JobRecord(
                job_id=f"JOB-{uuid4().hex[:18].upper()}", name="runtime_probe", tenant_id="runtime-certification",
                status="RUNNING", payload={"marker": marker}, attempts=1, locked_by="simulated-dead-worker",
                idempotency_key=f"crash-recovery:{marker}",
            )
            manager._save(job)
            manager.client.zadd(manager.running_key, {job.job_id: time.time() - 5})
            manager.client.delete(manager._lease_key(job.job_id))
            recovery = manager.recover_stale(limit=10)
            current_after_recovery = manager.get(job.job_id, tenant_id="runtime-certification")
            # The independent worker also runs recover_stale(). It may win the race before the certifier.
            # Accept that only when the job has visibly left the stale RUNNING state.
            recovery_observed = bool(
                recovery.get("recovered") == 1
                or (current_after_recovery and current_after_recovery.status in {"QUEUED", "SUCCEEDED"})
                or (current_after_recovery and current_after_recovery.status == "RUNNING" and current_after_recovery.locked_by != "simulated-dead-worker")
            )
            if not recovery_observed:
                return CheckResult("worker_crash_recovery", "FAIL", "expired worker lease was not requeued or claimed by an independent worker", {"recovery": recovery, "job_id": job.job_id, "status": getattr(current_after_recovery, "status", None)})
            deadline = time.time() + 30
            finished = None
            while time.time() < deadline:
                finished = manager.get(job.job_id, tenant_id="runtime-certification")
                if finished and finished.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                    break
                time.sleep(0.5)
            ok = bool(
                finished and finished.status == "SUCCEEDED"
                and (finished.result or {}).get("marker") == marker
                and finished.completed_by and finished.completed_by != manager.worker_id
            )
            return CheckResult(
                "worker_crash_recovery", "PASS" if ok else "FAIL",
                "expired worker lease was recovered and completed by an independent worker" if ok else "recovered job was not completed by an independent worker",
                {
                    "job_id": job.job_id, "recovery": recovery, "status": getattr(finished, "status", None),
                    "completed_by": getattr(finished, "completed_by", "") if finished else "",
                },
            )
        except Exception as exc:
            return CheckResult("worker_crash_recovery", "FAIL", str(exc), {})

    def check_storage(self, *, destructive_roundtrip: bool = False) -> CheckResult:
        provider = self.settings.storage_provider
        if provider == "local":
            return CheckResult("object_storage", "NOT_VERIFIED", "local storage is a development runtime, not production object storage", {"provider": "local"})
        if provider != "s3":
            return CheckResult("object_storage", "FAIL", f"unsupported storage provider: {provider}", {"provider": provider})
        if not destructive_roundtrip:
            return CheckResult("object_storage", "NOT_VERIFIED", "S3 is configured but private round-trip was not requested", {"provider": "s3"})
        marker = f"runtime-certification-{uuid4().hex}.txt"
        content = f"CareerOS runtime certification {datetime.now(timezone.utc).isoformat()}".encode()
        try:
            stored = self.object_storage.put(tenant_id="runtime-certification", owner_id="system", filename=marker, content=content, content_type="text/plain")
            read_back = self.object_storage.get(stored.key)
            if hashlib.sha256(read_back).hexdigest() != hashlib.sha256(content).hexdigest():
                raise StorageError("round-trip checksum mismatch")
            signed_url = self.object_storage.presigned_get_url(stored.key, expires_seconds=60)
            # A generated URL is not sufficient evidence: perform a real HTTP GET. For local Docker MinIO,
            # the browser-facing signed URL may use localhost while the certifier must transport the request
            # over Docker DNS. In that case rewrite only the transport destination and preserve the signed Host.
            fetch_url = signed_url
            fetch_headers: dict[str, str] = {}
            fetch_endpoint = str(getattr(self.settings, "s3_certification_fetch_endpoint", "") or "").strip()
            if fetch_endpoint:
                public_parts = urlparse(signed_url)
                fetch_parts = urlparse(fetch_endpoint)
                fetch_url = urlunparse((
                    fetch_parts.scheme or public_parts.scheme, fetch_parts.netloc, public_parts.path,
                    public_parts.params, public_parts.query, public_parts.fragment,
                ))
                if public_parts.netloc:
                    fetch_headers["Host"] = public_parts.netloc
            response = httpx.get(fetch_url, timeout=15, follow_redirects=True, headers=fetch_headers)
            if response.status_code != 200:
                raise StorageError(f"presigned HTTP GET failed with status {response.status_code}")
            if hashlib.sha256(response.content).hexdigest() != hashlib.sha256(content).hexdigest():
                raise StorageError("presigned HTTP GET checksum mismatch")
            self.object_storage.delete(stored.key)
            return CheckResult(
                "object_storage", "PASS",
                "private object put/SDK-get/presigned-HTTP-get/delete round-trip succeeded",
                {
                    "provider": "s3", "sha256": stored.sha256,
                    "presigned_url_generated": bool(signed_url),
                    "presigned_http_status": response.status_code,
                    "presigned_http_checksum_match": True,
                    "presigned_public_host": urlparse(signed_url).netloc,
                    "certification_fetch_host": urlparse(fetch_url).netloc,
                },
            )
        except Exception as exc:
            return CheckResult("object_storage", "FAIL", str(exc), {"provider": "s3"})

    def check_observability(self) -> CheckResult:
        url = str(getattr(self.settings, "observability_certification_url", "") or "").strip()
        if not url:
            return CheckResult("observability_sink", "NOT_CONFIGURED", "OBSERVABILITY_CERTIFICATION_URL is not configured", {})
        try:
            response = httpx.get(url, timeout=10, follow_redirects=True)
            ok = 200 <= response.status_code < 300
            return CheckResult(
                "observability_sink", "PASS" if ok else "FAIL",
                "external observability health endpoint responded successfully" if ok else f"observability endpoint returned HTTP {response.status_code}",
                {"status_code": response.status_code, "url_host": urlparse(url).hostname or ""},
            )
        except Exception as exc:
            return CheckResult("observability_sink", "FAIL", str(exc), {"url_host": urlparse(url).hostname or ""})

    def check_embedding(self) -> CheckResult:
        if not self.embedding_gateway.semantic_enabled:
            return CheckResult("semantic_embedding", "NOT_CONFIGURED", "semantic embedding provider is not configured", {"provider": self.embedding_gateway.config.provider})
        try:
            result = self.embedding_gateway.embed(["CareerOS runtime semantic embedding certification marker"])
        except Exception as exc:
            return CheckResult("semantic_embedding", "FAIL", str(exc), {"provider": self.embedding_gateway.config.provider})
        if result.provider == "local_hash":
            return CheckResult("semantic_embedding", "FAIL", result.warning or "remote provider fell back to local_hash", {"provider": result.provider, "model": result.model})
        return CheckResult("semantic_embedding", "PASS", "remote semantic embedding call succeeded", {"provider": result.provider, "model": result.model, "dimensions": result.dimensions})

    async def check_llm(self) -> CheckResult:
        if self.model_store is None or self.llm_gateway is None:
            return CheckResult("llm", "NOT_VERIFIED", "LLM runtime is not attached to certifier", {})
        providers = [p for p in self.model_store.list_providers() if p.get("enabled", True)]
        if not providers:
            return CheckResult("llm", "NOT_CONFIGURED", "no enabled provider is configured", {})
        failures: list[str] = []
        for provider in providers:
            provider_id = provider["provider_id"]
            try:
                result = await self.llm_gateway.test_provider(provider_id)
                return CheckResult("llm", "PASS", "live provider connectivity test succeeded", {k: result.get(k) for k in ("provider_id", "model", "latency_ms")})
            except Exception as exc:
                failures.append(f"{provider_id}: {exc}")
        return CheckResult("llm", "FAIL", "; ".join(failures[:5]) or "all enabled providers failed", {"providers_tested": len(providers)})

    async def run(self, *, storage_roundtrip: bool = False, include_llm: bool = True, profile: str = "full") -> dict[str, Any]:
        profile_name = (profile or "full").strip().lower()
        checks = [self.check_postgres(), self.check_pgvector(), self.check_redis(), self.check_distributed_rate_limit(), self.check_background_jobs(), self.check_worker_crash_recovery(), self.check_storage(destructive_roundtrip=storage_roundtrip), self.check_embedding(), self.check_observability()]
        if include_llm:
            checks.append(await self.check_llm())
        else:
            checks.append(CheckResult("llm", "NOT_VERIFIED", "LLM check was explicitly skipped", {}, required=profile_name == "full"))

        if profile_name == "infrastructure":
            required_names = {"postgresql", "pgvector", "redis", "distributed_rate_limit", "redis_background_jobs", "worker_crash_recovery", "object_storage", "observability_sink"}
        elif profile_name == "ai":
            required_names = {"semantic_embedding", "llm"}
        else:
            required_names = {c.name for c in checks}
            profile_name = "full"
        for c in checks:
            c.required = c.name in required_names
        all_required_pass = all(c.status == "PASS" for c in checks if c.required)
        return {
            "format": "careeros-runtime-certification-v2",
            "certification_version": "1.0-beta1",
            "profile": profile_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": self.settings.app_env,
            "environment_fingerprint": runtime_environment_fingerprint(self.settings),
            "all_required_pass": all_required_pass,
            "checks": [asdict(c) for c in checks],
        }


def write_certification(report: dict[str, Any], path: str, *, secret_key: str) -> dict[str, Any]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    signed = sign_runtime_certification(report, secret_key)
    target.write_text(json.dumps(signed, ensure_ascii=False, indent=2), encoding="utf-8")
    return signed
