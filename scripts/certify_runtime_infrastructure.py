from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import Settings
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.runtime_certification import RuntimeCertification, runtime_environment_fingerprint
from app.storage import S3CompatibleStorageAdapter


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Probe externally backed runtime infrastructure without claiming "
            "full Runtime Verified status."
        )
    )
    parser.add_argument(
        "--out",
        default="data/runtime_infrastructure_probe.json",
        help="JSON report path.",
    )
    args = parser.parse_args()

    settings = Settings()
    embedding_gateway = EmbeddingGateway(
        EmbeddingConfig(
            provider=settings.embedding_provider,
            base_url=settings.embedding_base_url,
            api_key=settings.embedding_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.embedding_timeout_seconds,
            max_batch_size=settings.embedding_max_batch_size,
            max_retries=settings.embedding_max_retries,
            retry_backoff_seconds=settings.embedding_retry_backoff_seconds,
        )
    )
    storage = S3CompatibleStorageAdapter(
        endpoint=settings.s3_endpoint,
        bucket=settings.s3_bucket,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        region=settings.s3_region,
        public_endpoint=settings.s3_public_endpoint,
    )
    certification = RuntimeCertification(
        settings=settings,
        embedding_gateway=embedding_gateway,
        object_storage=storage,
    )

    checks = [
        certification.check_postgres(),
        certification.check_pgvector(),
        certification.check_redis(),
        certification.check_distributed_rate_limit(),
        certification.check_background_jobs(),
        certification.check_worker_crash_recovery(),
        certification.check_storage(destructive_roundtrip=True),
    ]
    all_selected_pass = all(check.status == "PASS" for check in checks)
    payload = {
        "format": "careeros-runtime-infrastructure-probe-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "certification_scope": "infrastructure-only",
        "signed": False,
        "runtime_verified": False,
        "all_selected_pass": all_selected_pass,
        "environment_fingerprint": runtime_environment_fingerprint(settings),
        "checks": [dataclasses.asdict(check) for check in checks],
        "excluded_full_gates": [
            "semantic_embedding",
            "generation_model",
            "observability_sink",
            "business_e2e",
        ],
        "statement": (
            "This unsigned, environment-bound probe covers selected runtime "
            "infrastructure only. It is not a full Runtime Verified certificate."
        ),
    }

    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if all_selected_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
