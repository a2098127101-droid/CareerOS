from __future__ import annotations

import ast
from pathlib import Path


def test_worker_does_not_import_fastapi_main():
    source = Path("scripts/run_worker.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert "app.main" not in imported


def test_job_handlers_are_shared_between_api_and_worker():
    main = Path("app/main.py").read_text(encoding="utf-8")
    worker = Path("scripts/run_worker.py").read_text(encoding="utf-8")
    assert "register_background_handlers" in main
    assert "register_background_handlers" in worker


def test_staging_compose_contains_real_runtime_services_and_gate():
    text = Path("deploy/docker-compose.staging.yml").read_text(encoding="utf-8")
    for token in ("pgvector/pgvector:pg16", "redis:7-alpine", "minio/minio", "worker:", "certifier:", "staging_runtime_gate.py"):
        assert token in text
    assert "profiles: [\"certify\"]" in text
