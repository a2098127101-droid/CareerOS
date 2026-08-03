from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.auth_store import AuthStore
from app.core.database import BASELINE_METADATA, database_capabilities
from app.domain.profile import ParticipantProfile
from app.domain.roles import canonical_role, storage_role
from app.domain_profile import get_domain_profile
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.migrations import run_migrations
from app.models import StudentProfile, TenantProductConfigRequest
from app.repositories import RepositoryContainer
from app.store import SessionStore
from scripts.export_sqlite_snapshot import export_snapshot
from scripts.import_snapshot_to_postgres import import_snapshot


def test_baseline_metadata_is_postgresql_compilable_and_complete():
    required = {
        "tenants", "users", "tenant_memberships", "sessions", "workflow_instances", "workflow_steps",
        "artifact_series", "artifact_versions", "evidence_items", "evidence_claims", "evidence_graph_edges",
        "knowledge_sources", "knowledge_chunks", "jobs", "analytics_events", "llm_usage", "stored_objects",
    }
    assert required.issubset(BASELINE_METADATA.tables)
    for table in BASELINE_METADATA.tables.values():
        sql = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert "CREATE TABLE" in sql


def test_repository_container_preserves_sqlite_runtime(tmp_path: Path):
    db = tmp_path / "repo.db"
    run_migrations(str(db))
    gateway = EmbeddingGateway(EmbeddingConfig(provider="local_hash", model="local-hash-v1", dimensions=64))
    repos = RepositoryContainer.build_sqlite(
        db_path=str(db), app_secret_key="x" * 40, session_ttl_hours=24,
        embedding_gateway=gateway, database_url="", app_env="development",
    )
    assert repos.backend == "sqlite"
    state = repos.sessions.create(tenant_id="demo-org", student_id="demo")
    assert repos.sessions.get(state.session_id).session_id == state.session_id


def test_database_readiness_fails_closed_for_real_production_sqlite():
    report = database_capabilities(
        database_url="", db_path="data/agent.db", repository_backend="sqlite", app_env="production"
    )
    assert report.production_ready is False
    assert any("PostgreSQL" in item for item in report.blockers)


def test_generic_role_aliases_and_enterprise_preset():
    assert canonical_role("student") == "participant"
    assert canonical_role("teacher") == "advisor"
    assert canonical_role("school_admin") == "organization_admin"
    assert storage_role("participant") == "student"
    assert storage_role("advisor") == "teacher"
    profile = get_domain_profile("enterprise_talent")
    assert profile.profile_id == "enterprise_talent"
    assert profile.has("talent_assessment")
    req = TenantProductConfigRequest(product_preset="enterprise_talent", tenant_type="enterprise")
    assert req.product_preset == "enterprise_talent"


def test_participant_profile_maps_legacy_profile_without_losing_compatibility():
    legacy = StudentProfile(
        name="Demo User", school="Demo Organization", major="General Background", grade="Stage 2",
        skills=["analysis"], projects=["project a"], target_job="Target Opportunity", evidence_text="verified input",
    )
    general = ParticipantProfile.from_legacy(legacy)
    assert general.display_name == "Demo User"
    assert general.organization_context == "Demo Organization"
    assert general.target_opportunity == "Target Opportunity"
    assert general.custom_attributes["major"] == "General Background"


def test_snapshot_export_and_postgres_import_dry_run(tmp_path: Path):
    db = tmp_path / "legacy.db"
    run_migrations(str(db))
    SessionStore(str(db)).create(tenant_id="demo-org", student_id="demo")
    # Create auth tables/data to ensure the snapshot covers identity tables as well.
    auth = AuthStore(str(db))
    auth.ensure_tenant("demo-org", "Demo Organization")
    auth.ensure_user(
        email="user@example.test", password="LongDemoPassword!", display_name="Demo User",
        tenant_id="demo-org", role="participant",
    )
    out = tmp_path / "snapshot"
    manifest = export_snapshot(db, out)
    assert manifest["tables"]["sessions"] == 1
    for table, expected_hash in manifest["sha256"].items():
        payload = (out / f"{table}.jsonl").read_bytes()
        assert b"\r\n" not in payload
        assert hashlib.sha256(payload).hexdigest() == expected_hash
    dry = import_snapshot(out, "", dry_run=True)
    assert dry["ok"] is True and dry["dry_run"] is True
    assert "sessions" in dry["order"]


def test_alembic_baseline_upgrade_on_fresh_sqlite(tmp_path: Path):
    root = Path(__file__).parents[1]
    target = tmp_path / "alembic.db"
    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = f"sqlite:///{target}"
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=root, env=env, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    import sqlite3
    with sqlite3.connect(target) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='sessions'").fetchone()[0]
    assert version == "0012_project_tenant_rls"
    assert count == 1


def test_sqlalchemy_session_repository_parity_on_baseline_schema(tmp_path: Path):
    from app.core.database import create_database_engine
    from app.repositories.postgres import PostgresSessionRepository
    db = tmp_path / "sqlalchemy-session.db"
    engine = create_database_engine("", str(db))
    BASELINE_METADATA.create_all(engine)
    repo = PostgresSessionRepository(engine, BASELINE_METADATA)
    created = repo.create(tenant_id="org-a", student_user_id="USR-1", class_id="group-a", student_id="USR-1")
    loaded = repo.get(created.session_id, tenant_id="org-a", student_user_id="USR-1")
    assert loaded.session_id == created.session_id
    loaded.stage = "draft"
    repo.save(loaded)
    rows = repo.list(tenant_id="org-a", class_id="group-a")
    assert rows and rows[0][0].stage == "draft"
