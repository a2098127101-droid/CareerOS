from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.bootstrap import bootstrap_model_config
from app.config import Settings
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.llm_gateway import LLMGateway
from app.repositories import RepositoryContainer
from app.runtime_certification import RuntimeCertification, write_certification
from app.storage import LocalStorageAdapter, S3CompatibleStorageAdapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Run live CareerOS runtime certification. PASS is never inferred from configuration alone.")
    parser.add_argument("--out", default="data/runtime_certification.json")
    parser.add_argument("--profile", choices=["full", "infrastructure", "ai"], default="full")
    parser.add_argument("--storage-roundtrip", action="store_true", help="Perform temporary private S3 put/get/presign/delete round-trip.")
    parser.add_argument("--skip-llm", action="store_true", help="Explicitly skip live LLM call. Full profile will then remain NOT READY.")
    args = parser.parse_args()

    settings = Settings()
    embedding = EmbeddingGateway(EmbeddingConfig(
        provider=settings.embedding_provider, base_url=settings.embedding_base_url, api_key=settings.embedding_api_key,
        model=settings.embedding_model, dimensions=settings.embedding_dimensions, timeout_seconds=settings.embedding_timeout_seconds,
        max_batch_size=settings.embedding_max_batch_size, max_retries=settings.embedding_max_retries,
        retry_backoff_seconds=settings.embedding_retry_backoff_seconds,
    ))
    if settings.storage_provider == "s3":
        storage = S3CompatibleStorageAdapter(endpoint=settings.s3_endpoint, bucket=settings.s3_bucket, access_key=settings.s3_access_key, secret_key=settings.s3_secret_key, region=settings.s3_region, public_endpoint=settings.s3_public_endpoint)
    else:
        storage = LocalStorageAdapter(settings.storage_local_root)

    if settings.repository_backend == "postgresql":
        repositories = RepositoryContainer.build_postgresql(
            db_path=settings.db_path, database_url=settings.database_url, app_secret_key=settings.app_secret_key,
            session_ttl_hours=settings.session_ttl_hours, embedding_gateway=embedding, app_env=settings.app_env,
        )
    else:
        repositories = RepositoryContainer.build_sqlite(
            db_path=settings.db_path, database_url=settings.database_url, app_secret_key=settings.app_secret_key,
            session_ttl_hours=settings.session_ttl_hours, embedding_gateway=embedding, app_env=settings.app_env,
        )
    model_store = repositories.models
    bootstrap_model_config(model_store, settings)
    gateway = LLMGateway(
        model_store,
        retry_attempts=settings.llm_retry_attempts,
        retry_backoff_seconds=settings.llm_retry_backoff_seconds,
        circuit_failure_threshold=settings.llm_circuit_failure_threshold,
        circuit_cooldown_seconds=settings.llm_circuit_cooldown_seconds,
        pii_redaction_enabled=settings.pii_redaction_enabled,
    )
    certifier = RuntimeCertification(settings=settings, embedding_gateway=embedding, object_storage=storage, model_store=model_store, llm_gateway=gateway)
    report = asyncio.run(certifier.run(storage_roundtrip=args.storage_roundtrip, include_llm=not args.skip_llm, profile=args.profile))
    signed = write_certification(report, args.out, secret_key=settings.app_secret_key)
    print(f"wrote {args.out}")
    for check in signed["checks"]:
        marker = "required" if check.get("required") else "optional"
        print(f"{check['name']}: {check['status']} ({marker}) - {check['detail']}")
    return 0 if signed["all_required_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
