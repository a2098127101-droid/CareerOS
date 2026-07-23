from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.background_jobs import build_job_manager
from app.config import Settings
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.job_handlers import register_background_handlers
from app.repositories import RepositoryContainer


def build_worker_runtime():
    settings = Settings()
    errors = settings.validate_runtime()
    if errors:
        raise RuntimeError("Worker runtime validation failed: " + "; ".join(errors))
    embedding = EmbeddingGateway(EmbeddingConfig(
        provider=settings.embedding_provider,
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        timeout_seconds=settings.embedding_timeout_seconds,
        max_batch_size=settings.embedding_max_batch_size,
        max_retries=settings.embedding_max_retries,
        retry_backoff_seconds=settings.embedding_retry_backoff_seconds,
    ))
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
    manager = build_job_manager(
        backend=settings.background_job_backend,
        redis_url=settings.redis_url,
        max_workers=settings.background_job_workers,
        ttl_seconds=settings.background_job_ttl_seconds,
        max_attempts=settings.background_job_max_attempts,
    )
    register_background_handlers(manager, knowledge_store=repositories.knowledge)
    return settings, manager


def main() -> int:
    try:
        settings, background_jobs = build_worker_runtime()
    except Exception as exc:
        print(f"worker startup failed: {exc}", file=sys.stderr)
        return 2
    if not hasattr(background_jobs, "work_once"):
        print("BACKGROUND_JOB_BACKEND must be redis to run a separate worker process.")
        return 2
    print(f"CareerOS worker started. backend={settings.background_job_backend}. Waiting for jobs...")
    while True:
        try:
            if hasattr(background_jobs, "recover_stale"):
                recovered = background_jobs.recover_stale(limit=100)
                if recovered.get("recovered") or recovered.get("failed"):
                    print(f"worker recovered stale jobs: {recovered}")
            background_jobs.work_once(timeout_seconds=5)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:
            print(f"worker error: {exc}", file=sys.stderr)
            time.sleep(2)


if __name__ == "__main__":
    raise SystemExit(main())
