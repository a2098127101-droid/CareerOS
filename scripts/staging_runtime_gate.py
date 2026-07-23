from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import bootstrap_model_config
from app.config import Settings
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.llm_gateway import LLMGateway
from app.repositories import RepositoryContainer
from app.runtime_certification import RuntimeCertification, load_runtime_certification, write_certification
from app.business_certification import BusinessE2ECertification, load_business_certification, write_business_certification
from scripts.certify_backup_restore import certify as certify_backup_restore
from scripts.certify_sqlite_postgres_migration import certify as certify_sqlite_postgres_migration
from scripts.certify_load_smoke import certify as certify_load_smoke
from scripts.staging_preflight import inspect as staging_preflight
from app.storage import LocalStorageAdapter, S3CompatibleStorageAdapter


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def _api_probe(base_url: str) -> dict:
    base = base_url.rstrip("/")
    with httpx.Client(timeout=10) as client:
        live = client.get(base + "/live")
        ready = client.get(base + "/ready")
    return {
        "live_status": live.status_code,
        "live_ok": live.status_code == 200 and bool(live.json().get("ok")),
        "ready_status": ready.status_code,
        "ready": ready.json() if "application/json" in ready.headers.get("content-type", "") else {"body": ready.text[:500]},
    }


async def _certify(settings: Settings, *, storage_roundtrip: bool) -> dict:
    embedding = EmbeddingGateway(EmbeddingConfig(
        provider=settings.embedding_provider, base_url=settings.embedding_base_url, api_key=settings.embedding_api_key,
        model=settings.embedding_model, dimensions=settings.embedding_dimensions, timeout_seconds=settings.embedding_timeout_seconds,
        max_batch_size=settings.embedding_max_batch_size, max_retries=settings.embedding_max_retries,
        retry_backoff_seconds=settings.embedding_retry_backoff_seconds,
    ))
    repositories = RepositoryContainer.build_postgresql(
        db_path=settings.db_path, database_url=settings.database_url, app_secret_key=settings.app_secret_key,
        session_ttl_hours=settings.session_ttl_hours, embedding_gateway=embedding, app_env=settings.app_env,
    ) if settings.repository_backend == "postgresql" else RepositoryContainer.build_sqlite(
        db_path=settings.db_path, database_url=settings.database_url, app_secret_key=settings.app_secret_key,
        session_ttl_hours=settings.session_ttl_hours, embedding_gateway=embedding, app_env=settings.app_env,
    )
    bootstrap_model_config(repositories.models, settings)
    gateway = LLMGateway(
        repositories.models, retry_attempts=settings.llm_retry_attempts,
        retry_backoff_seconds=settings.llm_retry_backoff_seconds,
        circuit_failure_threshold=settings.llm_circuit_failure_threshold,
        circuit_cooldown_seconds=settings.llm_circuit_cooldown_seconds,
        pii_redaction_enabled=settings.pii_redaction_enabled,
    )
    storage = S3CompatibleStorageAdapter(
        endpoint=settings.s3_endpoint, bucket=settings.s3_bucket, access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key, region=settings.s3_region, public_endpoint=settings.s3_public_endpoint,
    ) if settings.storage_provider == "s3" else LocalStorageAdapter(settings.storage_local_root)
    certifier = RuntimeCertification(settings=settings, embedding_gateway=embedding, object_storage=storage, model_store=repositories.models, llm_gateway=gateway)
    return await certifier.run(storage_roundtrip=storage_roundtrip, include_llm=True, profile="full")


def main() -> int:
    parser = argparse.ArgumentParser(description="CareerOS beta1 staging gate: migrations -> repository cert -> runtime cert -> business E2E -> DR cert -> readiness.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--storage-roundtrip", action="store_true")
    parser.add_argument("--skip-migrations", action="store_true")
    parser.add_argument("--skip-postgres-cert", action="store_true")
    parser.add_argument("--out", default="data/staging_gate_report.json")
    args = parser.parse_args()

    settings = Settings()
    if settings.repository_backend != "postgresql" or not settings.database_url:
        print("Staging gate requires REPOSITORY_BACKEND=postgresql and DATABASE_URL.", file=sys.stderr)
        return 2
    preflight = staging_preflight(settings, profile="full")
    if not preflight.get("ok"):
        print(json.dumps(preflight, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    if not args.skip_migrations:
        _run([sys.executable, "-m", "alembic", "upgrade", "head"])
    if not args.skip_postgres_cert:
        _run([sys.executable, "scripts/certify_postgres.py", "--database-url", settings.database_url, "--out", settings.postgres_certification_file])

    report = asyncio.run(_certify(settings, storage_roundtrip=args.storage_roundtrip))
    signed = write_certification(report, settings.runtime_certification_file, secret_key=settings.app_secret_key)
    verified = load_runtime_certification(settings.runtime_certification_file, settings=settings)

    # Business E2E uses the running API plus the same live repositories as production.
    repositories = RepositoryContainer.build_postgresql(
        db_path=settings.db_path, database_url=settings.database_url, app_secret_key=settings.app_secret_key,
        session_ttl_hours=settings.session_ttl_hours, embedding_gateway=EmbeddingGateway(EmbeddingConfig(
            provider=settings.embedding_provider, base_url=settings.embedding_base_url, api_key=settings.embedding_api_key,
            model=settings.embedding_model, dimensions=settings.embedding_dimensions, timeout_seconds=settings.embedding_timeout_seconds,
            max_batch_size=settings.embedding_max_batch_size, max_retries=settings.embedding_max_retries,
            retry_backoff_seconds=settings.embedding_retry_backoff_seconds,
        )), app_env=settings.app_env,
    )
    business_report = BusinessE2ECertification(settings=settings, repositories=repositories, base_url=args.base_url).run()
    signed_business = write_business_certification(business_report, settings.business_certification_file, secret_key=settings.app_secret_key)
    verified_business = load_business_certification(settings.business_certification_file, settings=settings)

    migration_certification = certify_sqlite_postgres_migration(settings.database_url)
    disaster_recovery = certify_backup_restore(settings.database_url)
    load_smoke = asyncio.run(certify_load_smoke(args.base_url, requests=100, concurrency=20, p95_limit_ms=1000.0))
    api_probe = _api_probe(args.base_url)
    gate = {
        "format": "careeros-staging-gate-v2",
        "preflight": preflight,
        "runtime_certification": signed,
        "runtime_certificate_valid": bool(verified.get("valid")),
        "runtime_certificate_reason": verified.get("reason", ""),
        "business_certification": signed_business,
        "business_certificate_valid": bool(verified_business.get("valid")),
        "business_certificate_reason": verified_business.get("reason", ""),
        "migration_certification": migration_certification,
        "backup_restore_certification": disaster_recovery,
        "load_smoke_certification": load_smoke,
        "api_probe": api_probe,
        "pass": (
            bool(verified.get("valid"))
            and bool(verified_business.get("valid"))
            and bool(migration_certification.get("ok"))
            and bool(disaster_recovery.get("ok"))
            and bool(load_smoke.get("ok"))
            and bool(api_probe.get("live_ok"))
            and bool(api_probe.get("ready", {}).get("ready"))
        ),
    }
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(gate, ensure_ascii=False, indent=2))
    return 0 if gate["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
