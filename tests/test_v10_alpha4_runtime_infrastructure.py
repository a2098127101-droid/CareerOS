from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import pytest

from app.background_jobs import InProcessJobManager
from app.file_security import FileAccessSigner, UploadSecurityError, validate_upload
from app.runtime_state import MemoryRateLimiter
from app.storage import LocalStorageAdapter, StorageRegistry
from app.migrations import run_migrations, migration_status


def test_memory_rate_limiter_enforces_window():
    limiter = MemoryRateLimiter()
    assert limiter.allow(scope="login", key="127.0.0.1", limit=2, window_seconds=60)
    assert limiter.allow(scope="login", key="127.0.0.1", limit=2, window_seconds=60)
    assert not limiter.allow(scope="login", key="127.0.0.1", limit=2, window_seconds=60)
    assert limiter.capabilities()["distributed"] is False


def test_background_job_executes_and_is_tenant_scoped():
    manager = InProcessJobManager(max_workers=1)
    def handler(payload, progress):
        progress(50, "half")
        return {"value": payload["value"] * 2}
    manager.register("double", handler)
    job = manager.enqueue(name="double", payload={"value": 4}, tenant_id="tenant-a", user_id="u1")
    deadline = time.time() + 3
    current = None
    while time.time() < deadline:
        current = manager.get(job.job_id, tenant_id="tenant-a")
        if current and current.status in {"SUCCEEDED", "FAILED"}:
            break
        time.sleep(0.02)
    assert current is not None
    assert current.status == "SUCCEEDED"
    assert current.result == {"value": 8}
    assert manager.get(job.job_id, tenant_id="tenant-b") is None


def _docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("word/document.xml", "<w:document></w:document>")
    return buf.getvalue()


def test_upload_security_magic_mime_and_archive_policy():
    report = validate_upload(
        filename="sample.docx", content=_docx_bytes(),
        declared_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        max_bytes=1024 * 1024,
    )
    assert report.archive_entries == 2
    with pytest.raises(UploadSecurityError, match="PDF magic"):
        validate_upload(filename="fake.pdf", content=b"not-a-pdf", declared_type="application/pdf", max_bytes=1024)
    with pytest.raises(UploadSecurityError, match="unsupported file extension"):
        validate_upload(filename="run.exe", content=b"MZxxxx", max_bytes=1024)


def test_signed_file_token_is_bound_and_tamper_protected():
    signer = FileAccessSigner("x" * 40)
    signed = signer.issue(object_id="OBJ-1", tenant_id="tenant-a", ttl_seconds=60)
    payload = signer.verify(signed["token"], object_id="OBJ-1")
    assert payload["tenant_id"] == "tenant-a"
    with pytest.raises(UploadSecurityError):
        signer.verify(signed["token"] + "broken", object_id="OBJ-1")
    with pytest.raises(UploadSecurityError):
        signer.verify(signed["token"], object_id="OBJ-2")


def test_local_storage_registry_private_lifecycle(tmp_path: Path):
    db = tmp_path / "app.db"
    run_migrations(str(db))
    adapter = LocalStorageAdapter(str(tmp_path / "uploads"))
    registry = StorageRegistry(str(db))
    stored = adapter.put(tenant_id="tenant-a", owner_id="user-a", filename="note.txt", content=b"hello", content_type="text/plain")
    meta = registry.record(stored=stored, tenant_id="tenant-a", owner_user_id="user-a", scan_status="clean")
    assert meta["status"] == "active"
    assert meta["scan_status"] == "clean"
    assert adapter.get(meta["object_key"]) == b"hello"
    assert registry.get(stored.object_id, tenant_id="tenant-b") is None
    assert registry.mark_deleted(stored.object_id, tenant_id="tenant-a") is True
    assert registry.get(stored.object_id, tenant_id="tenant-a") is None


def test_alpha4_migration_is_latest(tmp_path: Path):
    db = tmp_path / "migration.db"
    run_migrations(str(db))
    status = migration_status(str(db))
    assert status["current"] >= 12
    assert status["latest"] >= 12


def test_background_job_retries_transient_failure():
    manager = InProcessJobManager(max_workers=1, max_attempts=2)
    calls = {"n": 0}
    def flaky(payload, progress):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("temporary")
        return {"ok": True}
    manager.register("flaky", flaky)
    job = manager.enqueue(name="flaky", payload={}, tenant_id="tenant-a")
    deadline = time.time() + 3
    current = None
    while time.time() < deadline:
        current = manager.get(job.job_id, tenant_id="tenant-a")
        if current and current.status in {"SUCCEEDED", "FAILED"}:
            break
        time.sleep(0.02)
    assert current is not None and current.status == "SUCCEEDED"
    assert current.attempts == 2
