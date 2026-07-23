from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.business_certification import BusinessE2ECertification, write_business_certification
from app.config import Settings
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.repositories import RepositoryContainer


def build_repositories(settings: Settings):
    embedding = EmbeddingGateway(EmbeddingConfig(
        provider=settings.embedding_provider, base_url=settings.embedding_base_url, api_key=settings.embedding_api_key,
        model=settings.embedding_model, dimensions=settings.embedding_dimensions, timeout_seconds=settings.embedding_timeout_seconds,
        max_batch_size=settings.embedding_max_batch_size, max_retries=settings.embedding_max_retries,
        retry_backoff_seconds=settings.embedding_retry_backoff_seconds,
    ))
    builder = RepositoryContainer.build_postgresql if settings.repository_backend == "postgresql" else RepositoryContainer.build_sqlite
    return builder(
        db_path=settings.db_path, database_url=settings.database_url, app_secret_key=settings.app_secret_key,
        session_ttl_hours=settings.session_ttl_hours, embedding_gateway=embedding, app_env=settings.app_env,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run authenticated CareerOS business E2E + semantic RAG + tenant-isolation certification.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--out", default="data/business_certification.json")
    args = parser.parse_args()
    settings = Settings()
    repositories = build_repositories(settings)
    report = BusinessE2ECertification(settings=settings, repositories=repositories, base_url=args.base_url).run()
    signed = write_business_certification(report, args.out, secret_key=settings.app_secret_key)
    print(f"wrote {args.out}")
    for check in signed["checks"]:
        print(f"{check['name']}: {check['status']} - {check['detail']}")
    return 0 if signed["all_required_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
