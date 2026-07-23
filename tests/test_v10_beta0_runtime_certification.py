from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings
from app.runtime_certification import (
    load_runtime_certification,
    runtime_environment_fingerprint,
    sign_runtime_certification,
    write_certification,
)


def _report(settings: Settings) -> dict:
    return {
        "format": "careeros-runtime-certification-v2",
        "certification_version": "1.0-beta0",
        "profile": "full",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": settings.app_env,
        "environment_fingerprint": runtime_environment_fingerprint(settings),
        "all_required_pass": True,
        "checks": [{"name": "probe", "status": "PASS", "detail": "ok", "evidence": {}, "required": True}],
    }


def test_runtime_certificate_is_signed_bound_and_fresh(tmp_path: Path):
    settings = replace(
        Settings(),
        app_secret_key="x" * 64,
        database_url="postgresql://user:secret@db.example.test:5432/careeros",
        redis_url="redis://redis.example.test:6379/0",
        storage_provider="s3",
        s3_endpoint="https://objects.example.test",
        s3_bucket="careeros-private",
        embedding_provider="openai_compatible",
        embedding_base_url="https://emb.example.test/v1",
        embedding_model="emb-v1",
        runtime_certification_max_age_hours=24,
    )
    target = tmp_path / "runtime-cert.json"
    write_certification(_report(settings), str(target), secret_key=settings.app_secret_key)
    loaded = load_runtime_certification(target, settings=settings)
    assert loaded["valid"] is True

    other = replace(settings, s3_bucket="different-bucket")
    assert load_runtime_certification(target, settings=other)["valid"] is False

    data = json.loads(target.read_text(encoding="utf-8"))
    data["checks"][0]["detail"] = "tampered"
    target.write_text(json.dumps(data), encoding="utf-8")
    tampered = load_runtime_certification(target, settings=settings)
    assert tampered["valid"] is False
    assert "signature" in tampered["reason"]


def test_runtime_certificate_expires(tmp_path: Path):
    settings = replace(Settings(), app_secret_key="y" * 64, runtime_certification_max_age_hours=1)
    report = _report(settings)
    report["generated_at"] = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    target = tmp_path / "stale.json"
    signed = sign_runtime_certification(report, settings.app_secret_key)
    target.write_text(json.dumps(signed), encoding="utf-8")
    loaded = load_runtime_certification(target, settings=settings)
    assert loaded["valid"] is False
    assert "stale" in loaded["reason"]


def test_incomplete_certificate_never_validates(tmp_path: Path):
    settings = replace(Settings(), app_secret_key="z" * 64)
    report = _report(settings)
    report["all_required_pass"] = False
    target = tmp_path / "failed.json"
    write_certification(report, str(target), secret_key=settings.app_secret_key)
    loaded = load_runtime_certification(target, settings=settings)
    assert loaded["valid"] is False
    assert "required runtime checks" in loaded["reason"]


def test_runtime_fingerprint_excludes_credentials_but_binds_targets():
    base = replace(
        Settings(),
        database_url="postgresql://user-a:secret-a@db.example.test:5432/careeros",
        redis_url="redis://:secret-a@redis.example.test:6379/0",
        storage_provider="s3",
        s3_endpoint="https://objects.example.test",
        s3_bucket="bucket-a",
    )
    rotated = replace(
        base,
        database_url="postgresql://user-b:secret-b@db.example.test:5432/careeros",
        redis_url="redis://:secret-b@redis.example.test:6379/0",
    )
    moved = replace(base, s3_bucket="bucket-b")
    assert runtime_environment_fingerprint(base) == runtime_environment_fingerprint(rotated)
    assert runtime_environment_fingerprint(base) != runtime_environment_fingerprint(moved)


def test_staging_preflight_rejects_placeholder_secrets():
    from scripts.staging_preflight import inspect
    settings = replace(
        Settings(),
        repository_backend="postgresql",
        database_url="postgresql://careeros:pw@postgres:5432/careeros",
        runtime_state_backend="redis",
        background_job_backend="redis",
        redis_url="redis://redis:6379/0",
        storage_provider="s3",
        s3_bucket="careeros-private",
        s3_access_key="CHANGE_ME_MINIO_ACCESS",
        s3_secret_key="CHANGE_ME_MINIO_SECRET",
        app_secret_key="CHANGE_ME_64_CHAR_RANDOM_SECRET",
    )
    report = inspect(settings)
    assert report["ok"] is False
    assert any("APP_SECRET_KEY" in x for x in report["errors"])
    assert any("S3" in x for x in report["errors"])
