from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from app.commercial_store import CommercialStore
from app.domain_profile import get_domain_profile
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.migrations import MIGRATIONS, run_migrations
from app.storage import LocalStorageAdapter, StorageRegistry, sanitize_filename


def test_default_domain_profile_is_generic():
    profile = get_domain_profile("career_development")
    assert profile.profile_id == "career_development"
    assert profile.enable_competition_template is False
    assert profile.member_label == "用户"


def test_embedding_gateway_truthful_local_fallback():
    gateway = EmbeddingGateway(EmbeddingConfig(provider="local_hash", dimensions=64))
    result = gateway.embed(["career development evidence", "another item"])
    assert result.provider == "local_hash"
    assert result.model == "local-hash-v1"
    assert gateway.semantic_enabled is False
    assert len(result.vectors) == 2
    assert len(result.vectors[0]) == 64


def test_commercial_plan_and_quota_foundation(tmp_path: Path):
    db = tmp_path / "commercial.db"
    run_migrations(str(db))
    store = CommercialStore(str(db))
    store.ensure_subscription("tenant-a", "free")
    sub = store.subscription("tenant-a")
    assert sub["plan_id"] == "free"
    assert sub["entitlements"]["advanced_review"] is False
    ok, reason = store.check_ai_quota("tenant-a")
    assert ok is True and reason == ""
    store.set_plan("tenant-a", "enterprise")
    assert store.entitlement("tenant-a", "team_workspace") is True


def test_local_storage_adapter_is_tenant_scoped_and_sanitized(tmp_path: Path):
    adapter = LocalStorageAdapter(str(tmp_path / "uploads"))
    stored = adapter.put(
        tenant_id="tenant-a", owner_id="user-a", filename="../unsafe name?.txt",
        content=b"hello", content_type="text/plain",
    )
    assert stored.provider == "local"
    assert "tenant-a" in stored.key
    assert "user-a" in stored.key
    assert ".." not in stored.filename
    assert Path(tmp_path / "uploads" / stored.key).exists()
    assert sanitize_filename("../../a?.pdf").endswith(".pdf")


def test_latest_migration_includes_commercial_and_storage_foundations():
    assert MIGRATIONS[-1][0] >= 9
    names = {name for _, name, _ in MIGRATIONS}
    assert "commercialization_foundation" in names
    assert "storage_foundation" in names


def test_showcase_has_no_personal_or_major_specific_demo_content():
    text = Path("CareerOS_H5_Showcase.html").read_text(encoding="utf-8")
    assert "DEMO SCENARIO · GENERIC PERSONA" in text
    assert "CareerOS Commercial Demo · v0.9" in text
    assert "Demo Advisor" in text


def test_generic_product_does_not_force_competition_track(monkeypatch, tmp_path: Path):
    # Import app against an isolated database. Demo mode keeps this deterministic and avoids real API calls.
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("PRODUCT_PRESET", "career_development")
    monkeypatch.setenv("AUTO_SEED_DEMO_USERS", "true")

    import importlib
    import app.main as main_module
    main_module = importlib.reload(main_module)
    client = TestClient(main_module.app)
    state = client.post("/api/sessions").json()
    response = client.post("/api/chat", json={"session_id": state["session_id"], "message": "帮我生成初稿"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "draft"
    assert "确认赛道" not in payload["reply"]


def test_readiness_truthfully_reports_sqlite_foundation(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "readiness.db"))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("AUTO_SEED_DEMO_USERS", "true")

    import importlib
    import app.main as main_module
    main_module = importlib.reload(main_module)
    client = TestClient(main_module.app)
    data = client.get("/api/admin/system/readiness").json()
    assert data["runtime"]["database_backend"] == "sqlite"
    assert data["runtime"]["semantic_embedding"] is False
    assert any("DEMO_MODE" in item for item in data["blockers"])
