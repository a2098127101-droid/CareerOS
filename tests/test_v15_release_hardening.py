from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.core.database import _tenant_from_parameters

ROOT = Path(__file__).parents[1]


def _alembic(target: Path, revision: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = f"sqlite:///{target}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


def test_published_0007_migration_remains_immutable():
    path = ROOT / "alembic" / "versions" / "0007_tenant_templates_evidence_risk.py"
    digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    assert digest == "847791a2f0146670aa72d2da32850dbcd9907bbe02f055e9cdbad41198930165"


def test_upgrade_from_original_0007_repairs_runtime_table(tmp_path: Path):
    target = tmp_path / "upgrade-from-published-0007.db"
    with sqlite3.connect(target) as conn:
        # Model a real deployment that already ran the published 0007 before
        # unified_runtime_entities was introduced. Using today's 0001 baseline
        # would incorrectly create every current manifest table up front.
        conn.executescript(
            """
            CREATE TABLE alembic_version (version_num VARCHAR(128) PRIMARY KEY);
            INSERT INTO alembic_version(version_num)
            VALUES ('0007_tenant_templates_evidence_risk');
            CREATE TABLE artifact_versions (
                version_id TEXT PRIMARY KEY,
                artifact_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                content TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                created_by TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                evidence_links_json TEXT NOT NULL DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    upgraded = _alembic(target, "head")
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    with sqlite3.connect(target) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(unified_runtime_entities)").fetchall()
        }
        indexes = {
            row[1] for row in conn.execute("PRAGMA index_list(artifact_versions)").fetchall()
        }
    assert version == "0010_immutable_runtime_tenant_hardening"
    assert {"tenant_id", "owner_user_id", "version", "revision", "updated_by"}.issubset(columns)
    assert "idx_artifact_versions_tenant" in indexes


def test_postgres_rls_context_extracts_explicit_repository_tenant():
    assert _tenant_from_parameters({"tenant": "org-a"}) == "org-a"
    assert _tenant_from_parameters({"tenant_id": "org-b"}) == "org-b"
    assert _tenant_from_parameters([{"target_tenant": "org-c"}]) == "org-c"
    assert _tenant_from_parameters({"other": "value"}) == ""


def test_rls_migration_is_postgres_only_and_has_read_write_policy():
    migration = (
        ROOT / "alembic" / "versions" / "0010_immutable_runtime_tenant_hardening.py"
    ).read_text(encoding="utf-8")
    assert 'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY' in migration
    assert 'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY' in migration
    assert "CREATE POLICY" in migration
    assert "WITH CHECK" in migration
    assert "app.tenant_id" in migration
    assert "app.platform_admin" in migration


def test_openapi_exposes_cookie_auth_and_canonical_v1_aliases(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("AGENT_DB_PATH", str(tmp_path / "openapi.db"))
    monkeypatch.setenv("AUTO_SEED_DEMO_USERS", "false")
    monkeypatch.setenv("AUTH_REQUIRED", "true")

    import importlib
    import app.main as main_module

    main_module = importlib.reload(main_module)
    schema = main_module.app.openapi()

    scheme = schema["components"]["securitySchemes"]["CareerOSSession"]
    assert scheme["type"] == "apiKey"
    assert scheme["in"] == "cookie"
    assert scheme["name"] == "careeros_session"
    assert "/api/v1/auth/me" in schema["paths"]
    assert "/api/v1/admin/models/overview" in schema["paths"]
    assert "/api/v1/health" in schema["paths"]
    assert schema["paths"]["/api/auth/me"]["get"]["deprecated"] is True
    assert schema["paths"]["/api/v1/auth/me"]["get"].get("deprecated") is not True
