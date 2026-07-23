from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath

_ROOT = _BootstrapPath(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import json
from dataclasses import asdict
from urllib.parse import urlparse

from app.config import Settings


def _placeholder(value: str) -> bool:
    raw = (value or "").strip().upper()
    return not raw or "CHANGE_ME" in raw or raw in {"SECRET", "PASSWORD", "EXAMPLE"}


def inspect(settings: Settings, profile: str = "infrastructure") -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    if settings.repository_backend != "postgresql" or not settings.database_url.startswith(("postgresql://", "postgres://")):
        errors.append("staging certification requires PostgreSQL repositories and DATABASE_URL")
    if settings.runtime_state_backend != "redis" or settings.background_job_backend != "redis" or not settings.redis_url:
        errors.append("staging certification requires Redis runtime state and Redis background jobs")
    if settings.storage_provider != "s3":
        errors.append("staging certification requires S3-compatible private object storage")
    if _placeholder(settings.app_secret_key) or len(settings.app_secret_key) < 32:
        errors.append("APP_SECRET_KEY must be replaced with a strong secret")
    if any(_placeholder(x) for x in (settings.s3_access_key, settings.s3_secret_key, settings.s3_bucket)):
        errors.append("S3 credentials/bucket contain empty or placeholder values")
    s3_host = (urlparse(settings.s3_endpoint).hostname or "").lower() if settings.s3_endpoint else ""
    public_host = (urlparse(settings.s3_public_endpoint).hostname or "").lower() if settings.s3_public_endpoint else ""
    if s3_host in {"minio", "s3", "object-storage"} and not settings.s3_public_endpoint:
        errors.append("S3_PUBLIC_ENDPOINT is required when S3_ENDPOINT uses a private container hostname")
    if public_host in {"localhost", "127.0.0.1"} and s3_host and s3_host != public_host and not settings.s3_certification_fetch_endpoint:
        errors.append("S3_CERTIFICATION_FETCH_ENDPOINT is required to certify a localhost-facing presigned URL from inside the container network")
    if settings.email_provider == "smtp" and (_placeholder(settings.smtp_host) or not settings.email_from):
        warnings.append("SMTP is not ready; identity emails will not be externally deliverable")
    if profile == "full":
        if settings.embedding_provider == "local_hash":
            errors.append("full certification requires a real semantic embedding provider, not local_hash")
        if settings.embedding_provider != "local_hash" and (not settings.embedding_base_url or not settings.embedding_api_key or not settings.embedding_model):
            errors.append("semantic embedding provider configuration is incomplete")
        if not settings.observability_certification_url:
            errors.append("full certification requires OBSERVABILITY_CERTIFICATION_URL")
    return {
        "ok": not errors,
        "profile": profile,
        "errors": errors,
        "warnings": warnings,
        "runtime": {
            "app_env": settings.app_env,
            "repository_backend": settings.repository_backend,
            "runtime_state_backend": settings.runtime_state_backend,
            "background_job_backend": settings.background_job_backend,
            "storage_provider": settings.storage_provider,
            "embedding_provider": settings.embedding_provider,
            "email_provider": settings.email_provider,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate beta1 staging configuration without contacting external dependencies.")
    parser.add_argument("--profile", choices=["infrastructure", "full"], default="infrastructure")
    args = parser.parse_args()
    report = inspect(Settings(), profile=args.profile)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
