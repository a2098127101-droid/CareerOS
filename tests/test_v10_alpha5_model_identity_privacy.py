from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

from app.auth_store import AuthStore
from app.core.database import BASELINE_METADATA
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.llm_gateway import LLMGateway
from app.migrations import migration_status, run_migrations
from app.model_store import ModelConfigStore
from app.models import ModelCapabilityUpsert, ProviderUpsert, RouteUpsert
from app.privacy import redact_pii
from app.repositories.container import RepositoryContainer


def test_alpha5_migration_is_latest_and_tables_exist(tmp_path: Path):
    db = tmp_path / "alpha5.db"
    run_migrations(str(db))
    status = migration_status(str(db))
    assert status["current"] >= 14
    import sqlite3
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"llm_model_capabilities", "model_eval_runs", "user_invitations", "privacy_consents", "data_subject_requests"} <= tables


def test_model_capability_registry_and_auto_recommendation(tmp_path: Path):
    db = tmp_path / "models.db"
    run_migrations(str(db))
    store = ModelConfigStore(str(db), "x" * 40)
    store.upsert_provider(ProviderUpsert(provider_id="p1", name="P1", kind="openai_compatible", base_url="https://example.invalid/v1", api_key="k", default_model="m1"))
    store.upsert_provider(ProviderUpsert(provider_id="p2", name="P2", kind="openai_compatible", base_url="https://example.invalid/v1", api_key="k", default_model="m2"))
    store.upsert_model_capability(ModelCapabilityUpsert(provider_id="p1", model="m1", supports_streaming=True, context_window=64000, latency_class="fast", input_cost_per_million=1, output_cost_per_million=2))
    store.upsert_model_capability(ModelCapabilityUpsert(provider_id="p2", model="m2", supports_streaming=False, context_window=128000, latency_class="slow", input_cost_per_million=0.5, output_cost_per_million=1))
    candidates = store.recommend_models(required_capabilities=["streaming"], min_context_window=32000, prefer_latency="fast")
    assert [c["model"] for c in candidates] == ["m1"]
    store.upsert_route(RouteUpsert(task="coach", provider_id="auto", model="auto", temperature=0.2, max_tokens=1000))
    gateway = LLMGateway(store)
    assert gateway._route_attempts("coach", store.get_route("coach"))[0] == ("p1", "m1")


def test_identity_invitation_lifecycle_and_privacy_records(tmp_path: Path):
    db = tmp_path / "identity.db"
    run_migrations(str(db))
    auth = AuthStore(str(db))
    auth.ensure_tenant("org-a", "Org A")
    admin = auth.create_user(email="admin@example.test", password="Password-12345", display_name="Admin", tenant_id="org-a", role="organization_admin")
    invite = auth.create_invitation(email="user@example.test", tenant_id="org-a", role="participant", invited_by=admin["user_id"], display_name="Demo User", ttl_hours=24)
    assert invite["token"]
    assert len(auth.list_invitations("org-a")) == 1
    user = auth.accept_invitation(invite["token"], "Password-12345")
    assert user["email"] == "user@example.test"
    assert auth.list_invitations("org-a") == []
    updated = auth.set_user_status(user_id=user["user_id"], tenant_id="org-a", status="disabled")
    assert updated["status"] == "disabled"
    auth.set_user_status(user_id=user["user_id"], tenant_id="org-a", status="active")
    changed = auth.change_membership_role(user_id=user["user_id"], tenant_id="org-a", role="advisor")
    assert changed["memberships"][0]["canonical_role"] == "advisor"
    consent = auth.record_consent(tenant_id="org-a", user_id=user["user_id"], policy_version="2026-01", purpose="service", granted=True)
    assert consent["granted"] is True
    assert auth.list_consents(tenant_id="org-a", user_id=user["user_id"])[0]["policy_version"] == "2026-01"
    dsr = auth.create_data_subject_request(tenant_id="org-a", user_id=user["user_id"], request_type="export")
    assert dsr["status"] == "pending"
    done = auth.update_data_subject_request(request_id=dsr["request_id"], tenant_id="org-a", status="completed", result={"format": "json"})
    assert done["status"] == "completed" and done["result"]["format"] == "json"


def test_sqlalchemy_identity_and_model_parity_for_alpha5(tmp_path: Path):
    db = tmp_path / "parity.db"
    engine = create_engine(f"sqlite:///{db.as_posix()}", future=True)
    BASELINE_METADATA.create_all(engine)
    repos = RepositoryContainer.build_sqlalchemy_core_for_testing(engine=engine, db_path=str(db), app_secret_key="x" * 40, session_ttl_hours=168, embedding_gateway=EmbeddingGateway(EmbeddingConfig()))
    identity = repos["identity"]
    identity.ensure_tenant("org-p", "Org P")
    admin = identity.create_user(email="admin@org.test", password="Password-12345", display_name="Admin", tenant_id="org-p", role="organization_admin")
    invite = identity.create_invitation(email="member@org.test", tenant_id="org-p", role="participant", invited_by=admin["user_id"])
    member = identity.accept_invitation(invite["token"], "Password-12345", "Member")
    assert member["memberships"][0]["canonical_role"] == "participant"
    identity.record_consent(tenant_id="org-p", user_id=member["user_id"], policy_version="v1")
    assert identity.list_consents(tenant_id="org-p", user_id=member["user_id"])

    models = repos["models"]
    models.upsert_provider(ProviderUpsert(provider_id="p0", name="Provider", kind="openai_compatible", base_url="https://example.invalid/v1", api_key="k", default_model="m"))
    models.upsert_model_capability(ModelCapabilityUpsert(provider_id="p0", model="m", supports_json_schema=True, context_window=64000))
    assert models.get_model_capability("p0", "m")["supports_json_schema"] is True
    models.record_model_eval(eval_id="MEVAL-1", tenant_id="org-p", task="profile", provider_id="p0", model="m", metrics={"success_rate":1.0}, cases=[])
    assert models.list_model_evals("org-p")[0]["metrics"]["success_rate"] == 1.0


def test_pii_redaction_is_deterministic_and_does_not_remove_normal_numbers():
    text = "Contact user@example.com or 13800138000. ID 11010519491231002X. Score 92 and year 2026 remain."
    result = redact_pii(text)
    assert "user@example.com" not in result.text
    assert "13800138000" not in result.text
    assert "11010519491231002X" not in result.text
    assert "Score 92" in result.text and "2026" in result.text
    assert result.counts["email"] == 1 and result.counts["phone"] == 1 and result.counts["id_number"] == 1
