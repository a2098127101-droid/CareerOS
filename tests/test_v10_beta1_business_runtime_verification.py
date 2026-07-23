from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path

from app.background_jobs import BackgroundJobManager, JobRecord, RedisJobManager
from app.business_certification import (
    load_business_certification,
    runtime_environment_fingerprint,
    write_business_certification,
)
from app.config import Settings
from app.runtime_certification import RuntimeCertification
from app.storage import StoredObject
from scripts.certify_sqlite_postgres_migration import _seed_fixture
from scripts.export_sqlite_snapshot import export_snapshot


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}
        self.zsets = {}

    def ping(self): return True
    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values: return False
        self.values[key] = str(value); return True
    def get(self, key): return self.values.get(key)
    def delete(self, key): self.values.pop(key, None); return 1
    def exists(self, key): return int(key in self.values)
    def expire(self, key, seconds): return int(key in self.values)
    def lpush(self, key, value): self.lists.setdefault(key, []).insert(0, str(value)); return len(self.lists[key])
    def brpop(self, key, timeout=1):
        values = self.lists.setdefault(key, [])
        if not values: return None
        return key, values.pop()
    def llen(self, key): return len(self.lists.get(key, []))
    def zadd(self, key, mapping): self.zsets.setdefault(key, {}).update({str(k): float(v) for k,v in mapping.items()}); return len(mapping)
    def zrem(self, key, member): return int(self.zsets.setdefault(key, {}).pop(str(member), None) is not None)
    def zrangebyscore(self, key, low, high, start=0, num=100):
        rows = [k for k,v in self.zsets.get(key, {}).items() if float(low) <= v <= float(high)]
        rows.sort(key=lambda k: self.zsets[key][k]); return rows[start:start+num]
    def zcard(self, key): return len(self.zsets.get(key, {}))


def _redis_manager(fake: FakeRedis) -> RedisJobManager:
    manager = object.__new__(RedisJobManager)
    BackgroundJobManager.__init__(manager)
    manager.client = fake
    manager.namespace = "test"
    manager.ttl_seconds = 3600
    manager.max_attempts = 3
    manager.worker_id = "worker-independent"
    manager.lease_seconds = 2
    return manager


def test_redis_job_records_completed_worker_and_recovers_stale_job():
    fake = FakeRedis(); manager = _redis_manager(fake)
    manager.register("runtime_probe", lambda payload, progress: {"marker": payload["marker"]})
    job = manager.enqueue(name="runtime_probe", payload={"marker":"x"}, tenant_id="t")
    assert manager.work_once(timeout_seconds=1) is True
    finished = manager.get(job.job_id, tenant_id="t")
    assert finished and finished.status == "SUCCEEDED"
    assert finished.completed_by == "worker-independent"

    stale = JobRecord(job_id="JOB-STALE", name="runtime_probe", tenant_id="t", status="RUNNING", attempts=1, locked_by="dead-worker")
    manager._save(stale)
    fake.zadd(manager.running_key, {stale.job_id: time.time()-10})
    recovered = manager.recover_stale()
    assert recovered["recovered"] == 1
    assert manager.get(stale.job_id, tenant_id="t").status == "QUEUED"


def test_runtime_storage_certification_performs_real_presigned_http_get(monkeypatch):
    class Storage:
        body = b""
        def put(self, **kwargs):
            self.body = kwargs["content"]
            return StoredObject("OBJ-1","s3","k","x.txt",len(self.body),__import__('hashlib').sha256(self.body).hexdigest(),"text/plain")
        def get(self, key): return self.body
        def presigned_get_url(self, key, expires_seconds=60): return "https://objects.invalid/signed"
        def delete(self, key): self.deleted = key
    storage = Storage()
    class Response:
        status_code = 200
        def __init__(self, body): self.content = body
    monkeypatch.setattr("app.runtime_certification.httpx.get", lambda *a, **k: Response(storage.body))
    settings = replace(Settings(), storage_provider="s3")
    certifier = RuntimeCertification(settings=settings, embedding_gateway=None, object_storage=storage)
    result = certifier.check_storage(destructive_roundtrip=True)
    assert result.status == "PASS"
    assert result.evidence["presigned_http_checksum_match"] is True


def test_business_certificate_is_signed_bound_and_fresh(tmp_path: Path):
    settings = replace(Settings(), app_secret_key="b"*64, business_certification_max_age_hours=24)
    report = {
        "format":"careeros-business-certification-v1", "certification_version":"1.0-beta1",
        "generated_at":__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
        "environment":settings.app_env, "environment_fingerprint":runtime_environment_fingerprint(settings),
        "all_required_pass":True, "checks":[{"name":"business_e2e","status":"PASS","detail":"ok","evidence":{},"required":True}],
    }
    target=tmp_path/"business.json"
    write_business_certification(report,str(target),secret_key=settings.app_secret_key)
    assert load_business_certification(target,settings=settings)["valid"] is True
    data=json.loads(target.read_text()); data["checks"][0]["detail"]="tampered"; target.write_text(json.dumps(data))
    assert load_business_certification(target,settings=settings)["valid"] is False


def test_migration_certification_fixture_exports_real_core_rows(tmp_path: Path):
    db = tmp_path/"fixture.db"; snapshot = tmp_path/"snapshot"
    fixture = _seed_fixture(db)
    manifest = export_snapshot(db, snapshot)
    assert fixture["session_id"]
    assert manifest["tables"].get("sessions",0) >= 1
    assert manifest["tables"].get("artifact_series",0) >= 1
    assert manifest["tables"].get("evidence_items",0) >= 1
    assert manifest["tables"].get("knowledge_sources",0) >= 1


def test_beta1_gate_requires_business_migration_and_recovery_certifications():
    text = Path("scripts/staging_runtime_gate.py").read_text(encoding="utf-8")
    assert "BusinessE2ECertification" in text
    assert "certify_sqlite_postgres_migration" in text
    assert "certify_backup_restore" in text
    assert "certify_load_smoke" in text
    assert "business_certificate_valid" in text
    assert "migration_certification" in text


def test_production_readiness_requires_business_certificate():
    text = Path("app/main.py").read_text(encoding="utf-8")
    assert "signed business E2E certification" in text
    assert "business_certification" in text


def test_worker_shared_handlers_include_runtime_probe_and_recovery_loop():
    handlers = Path("app/job_handlers.py").read_text(encoding="utf-8")
    worker = Path("scripts/run_worker.py").read_text(encoding="utf-8")
    assert 'job_manager.register("runtime_probe"' in handlers
    assert "recover_stale" in worker


def test_runtime_certifier_does_not_self_execute_worker_probe():
    text = Path("app/runtime_certification.py").read_text(encoding="utf-8")
    block = text[text.index("def check_background_jobs"):text.index("def check_storage")]
    assert ".work_once(" not in block
    assert "independent worker" in block.lower()


def test_business_certification_uses_ephemeral_credentials_and_deidentifies_users():
    text = Path("app/business_certification.py").read_text(encoding="utf-8")
    assert "secrets.token_urlsafe" in text
    assert "Certification-Only-Password-2026" not in text
    assert "anonymize_user_identity" in text
    assert "users_deidentified" in text


def test_business_cross_tenant_suite_covers_core_session_resources():
    text = Path("app/business_certification.py").read_text(encoding="utf-8")
    for marker in (
        '"workflow": b.get',
        '"evidence": b.get',
        '"evidence_graph": b.get',
        '"artifact_trace": b.get',
        '"file_access": b.get',
        '"job_match": b.post',
    ):
        assert marker in text


def test_stale_recovery_uses_per_job_atomic_recovery_lock():
    text = Path("app/background_jobs.py").read_text(encoding="utf-8")
    block = text[text.index("def recover_stale"):text.index("def retry", text.index("def recover_stale"))]
    assert "_recovery_key" in block
    assert "nx=True" in block
    assert "recovery_key" in block


def test_business_e2e_includes_job_intelligence_and_evidence_verification():
    text = Path("app/business_certification.py").read_text(encoding="utf-8")
    assert '"job intelligence"' in text
    assert '/evidence-verify' in text
    assert 'job_intelligence_statuses' in text



def test_presigned_certification_can_use_internal_transport_with_public_signed_host(monkeypatch):
    class Storage:
        body = b""
        def put(self, **kwargs):
            self.body = kwargs["content"]
            return StoredObject("OBJ-2","s3","bucket/k","x.txt",len(self.body),__import__('hashlib').sha256(self.body).hexdigest(),"text/plain")
        def get(self, key): return self.body
        def presigned_get_url(self, key, expires_seconds=60): return "http://127.0.0.1:9000/careeros-private/k?X-Signature=test"
        def delete(self, key): pass
    storage = Storage(); captured = {}
    class Response:
        status_code = 200
        def __init__(self, body): self.content = body
    def fake_get(url, **kwargs):
        captured["url"] = url; captured["headers"] = kwargs.get("headers") or {}
        return Response(storage.body)
    monkeypatch.setattr("app.runtime_certification.httpx.get", fake_get)
    settings = replace(Settings(), storage_provider="s3", s3_certification_fetch_endpoint="http://minio:9000")
    result = RuntimeCertification(settings=settings, embedding_gateway=None, object_storage=storage).check_storage(destructive_roundtrip=True)
    assert result.status == "PASS"
    assert captured["url"].startswith("http://minio:9000/")
    assert captured["headers"].get("Host") == "127.0.0.1:9000"
    assert result.evidence["presigned_public_host"] == "127.0.0.1:9000"


def test_staging_preflight_requires_public_endpoint_for_private_minio_hostname():
    from scripts.staging_preflight import inspect
    settings = replace(
        Settings(), repository_backend="postgresql", database_url="postgresql://careeros:pw@postgres:5432/careeros",
        runtime_state_backend="redis", background_job_backend="redis", redis_url="redis://redis:6379/0",
        storage_provider="s3", s3_endpoint="http://minio:9000", s3_public_endpoint="",
        s3_bucket="careeros-private", s3_access_key="minio-access", s3_secret_key="minio-secret-value",
        app_secret_key="z"*64,
    )
    report = inspect(settings)
    assert report["ok"] is False
    assert any("S3_PUBLIC_ENDPOINT" in error for error in report["errors"])
