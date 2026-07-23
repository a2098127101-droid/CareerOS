from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine

from app.core.database import BASELINE_METADATA
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.models import SessionState
from app.repositories.container import RepositoryContainer
from app.repositories.parity import CORE_PARITY


def build(tmp_path: Path):
    db = tmp_path / "repo_parity.db"
    engine = create_engine(f"sqlite:///{db.as_posix()}", future=True)
    BASELINE_METADATA.create_all(engine)
    repos = RepositoryContainer.build_sqlalchemy_core_for_testing(
        engine=engine,
        db_path=str(db),
        app_secret_key="x" * 40,
        session_ttl_hours=168,
        embedding_gateway=EmbeddingGateway(EmbeddingConfig()),
    )
    return engine, repos


def test_core_parity_report_is_explicit():
    assert set(CORE_PARITY.complete) >= {"sessions", "identity", "artifacts", "evidence", "workflows", "collaboration"}
    assert "knowledge" in CORE_PARITY.complete
    assert CORE_PARITY.code_parity_complete is True


def test_identity_session_tenant_isolation_parity(tmp_path):
    engine, r = build(tmp_path)
    identity = r["identity"]
    sessions = r["sessions"]
    identity.ensure_tenant("org-a", "Organization A")
    identity.ensure_tenant("org-b", "Organization B")
    a = identity.create_user(email="a@example.test", password="Password-12345", display_name="User A", tenant_id="org-a", role="participant")
    identity.create_user(email="b@example.test", password="Password-12345", display_name="User B", tenant_id="org-b", role="participant")
    principal, token = identity.authenticate("a@example.test", "Password-12345", tenant_id="org-a")
    assert principal.tenant_id == "org-a"
    assert identity.resolve_session(token).user_id == a["user_id"]
    state = sessions.create(tenant_id="org-a", student_user_id=a["user_id"], class_id="default", student_id="demo-a")
    assert sessions.get(state.session_id, tenant_id="org-a").tenant_id == "org-a"
    try:
        sessions.get(state.session_id, tenant_id="org-b")
        assert False, "cross-tenant session read must fail"
    except KeyError:
        pass


def test_artifact_evidence_workflow_collaboration_parity(tmp_path):
    engine, r = build(tmp_path)
    state = SessionState(session_id="S-1", tenant_id="org-a", student_id="user-a", student_user_id="user-a", class_id="default")
    r["sessions"].save(state)
    ev = r["evidence"].add("S-1", "student_input", "Profile", "Completed a structured customer interview project with 12 participants.", tenant_id="org-a")
    assert ev["evidence_id"].startswith("EVID-")
    assert len(r["evidence"].list_session("S-1", tenant_id="org-a")) == 1
    art1 = r["artifacts"].create_version("S-1", "report", "Development Report", "Version one", tenant_id="org-a", evidence_links=[{"evidence_id": ev["evidence_id"]}])
    art2 = r["artifacts"].create_version("S-1", "report_revision", "Development Report · 修订版", "Version two", tenant_id="org-a")
    assert art1["artifact_id"] == art2["artifact_id"]
    assert art2["version"] == 2
    assert len(r["artifacts"].list_versions(art1["artifact_id"], tenant_id="org-a")) == 2
    wf = r["workflows"].ensure(state, artifact_kinds={"report"})
    assert wf["session_id"] == "S-1"
    fb = r["collaboration"].add_feedback("S-1", "Clarify the evidence chain.", tenant_id="org-a", teacher_name="Demo Advisor")
    task = r["collaboration"].ensure_task("Revise evidence chain", "artifact_revision", "S-1", "org-a", source="feedback", payload={"feedback_id": fb["feedback_id"]})
    assert task["tenant_id"] == "org-a"
    assert r["collaboration"].get_task(task["task_id"], tenant_id="org-a")["payload"]["feedback_id"] == fb["feedback_id"]


def test_remaining_repository_adapters_smoke(tmp_path):
    engine, r = build(tmp_path)
    # Evidence graph
    ev = r["evidence"].add("S-graph", "student_input", "Demo", "Led 8 structured interviews and summarized findings.", tenant_id="org-x")
    art = r["artifacts"].create_version("S-graph", "report", "Report", "I led 8 structured interviews and summarized findings.", tenant_id="org-x")
    trace = r["evidence_graph"].trace_artifact_version(
        tenant_id="org-x", session_id="S-graph", artifact_id=art["artifact_id"], version_id=art["version_id"],
        content="I led 8 structured interviews and summarized findings.", evidence_items=[ev],
    )
    assert trace["claims"] >= 1
    # Knowledge
    src = r["knowledge"].ingest(title="Policy", filename="policy.txt", mime_type="text/plain", text="2026 career development policy requires evidence-based planning.", tenant_id="org-x", effective_year="2026", authority="official")
    hits = r["knowledge"].search("2026 evidence planning", tenant_id="org-x", effective_year="2026")
    assert src["source_id"] and hits
    # Jobs
    job = r["jobs"].upsert({"title":"Research Analyst","company":"Demo Co","skills":["interview","analysis"]}, tenant_id="org-x")
    assert r["jobs"].get(job["job_id"], tenant_id="org-x")["title"] == "Research Analyst"
    # Commercial / analytics
    r["commercial"].ensure_subscription("org-x", "professional")
    r["commercial"].set_plan("org-x", "professional")
    r["commercial"].track(tenant_id="org-x", event_name="login", user_id="U1")
    assert r["commercial"].analytics_summary("org-x")["events"]["login"] == 1
    # Storage registry
    from app.storage import StoredObject
    stored = StoredObject(object_id="OBJ-1", provider="local", key="org-x/U1/a.txt", filename="a.txt", size_bytes=1, sha256="x", content_type="text/plain")
    assert r["storage_registry"].record(stored=stored, tenant_id="org-x", owner_user_id="U1")["object_id"] == "OBJ-1"


def test_repository_parity_is_now_complete_but_live_postgres_unverified():
    assert CORE_PARITY.pending == ()
    assert CORE_PARITY.percent == 100
    assert CORE_PARITY.code_parity_complete is True
    assert CORE_PARITY.live_postgres_verified is False


def test_model_repository_adapter_roundtrip(tmp_path):
    engine, r = build(tmp_path)
    from app.models import ProviderUpsert, RouteUpsert
    models = r["models"]
    models.upsert_provider(ProviderUpsert(
        provider_id="demo-provider", name="Demo Provider", kind="openai_compatible",
        base_url="https://example.invalid/v1", api_key="secret-key-value",
        default_model="demo-model", enabled=True, timeout_seconds=30, extra_headers={"X-Demo":"1"},
    ))
    provider = models.get_provider("demo-provider")
    assert provider and provider.api_key == "secret-key-value"
    models.upsert_route(RouteUpsert(
        task="coach", provider_id="demo-provider", model="demo-model",
        fallback_provider_id=None, fallback_model=None, temperature=0.2, max_tokens=1000,
    ))
    assert models.get_route("coach").provider_id == "demo-provider"
    models.record_usage(task="coach", provider_id="demo-provider", model="demo-model", total_tokens=123, latency_ms=456, tenant_id="org-x")
    summary = models.usage_summary(tenant_id="org-x")
    assert summary["summary"]["calls"] == 1 and summary["summary"]["tokens"] == 123


def test_session_repository_metadata_assign_owner_and_updated_at(tmp_path):
    import time
    _, r = build(tmp_path)
    sessions = r["sessions"]
    state = sessions.create(tenant_id="org-a", student_user_id="u-a", class_id="g-a", student_id="p-a")
    before = sessions.metadata(state.session_id)
    time.sleep(0.01)
    assigned = sessions.assign_owner(state.session_id, tenant_id="org-b", student_user_id="u-b", class_id="g-b")
    after = sessions.metadata(state.session_id)
    assert assigned.tenant_id == "org-b"
    assert assigned.student_user_id == "u-b"
    assert after["tenant_id"] == "org-b" and after["class_id"] == "g-b"
    assert str(after["updated_at"]) >= str(before["updated_at"])


def test_cross_tenant_scope_for_knowledge_jobs_and_evidence_graph(tmp_path):
    _, r = build(tmp_path)
    r["knowledge"].ingest(
        title="Org A Policy", filename="a.txt", mime_type="text/plain",
        text="Organization A private development policy and internal evidence requirements.",
        tenant_id="org-a", scope="global", authority="internal",
    )
    hits_b = r["knowledge"].search("Organization A private development policy", tenant_id="org-b")
    assert not any(h.source_title == "Org A Policy" for h in hits_b)

    job = r["jobs"].upsert({"title": "Private Role", "company": "Org A"}, tenant_id="org-a")
    try:
        r["jobs"].get(job["job_id"], tenant_id="org-b")
        assert False, "cross-tenant job read must fail"
    except KeyError:
        pass

    ev = r["evidence"].add("S-A", "student_input", "Demo", "Completed 5 structured interviews.", tenant_id="org-a")
    art = r["artifacts"].create_version("S-A", "report", "Report", "Completed 5 structured interviews.", tenant_id="org-a")
    r["evidence_graph"].trace_artifact_version(
        tenant_id="org-a", session_id="S-A", artifact_id=art["artifact_id"], version_id=art["version_id"],
        content="Completed 5 structured interviews.", evidence_items=[ev],
    )
    graph_b = r["evidence_graph"].session_graph("S-A", tenant_id="org-b")
    assert graph_b.get("nodes", []) == [] and graph_b.get("edges", []) == []
