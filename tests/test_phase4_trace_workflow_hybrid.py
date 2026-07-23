from pathlib import Path

from app.artifact_store import ArtifactStore
from app.evidence_graph import EvidenceGraphStore
from app.evidence_store import EvidenceStore
from app.knowledge import KnowledgeStore
from app.migrations import migration_status, run_migrations
from app.models import SessionState
from app.workflow_store import WorkflowStore


def test_workflow_persists_completion_history(tmp_path: Path):
    db = str(tmp_path / "workflow.db")
    run_migrations(db)
    store = WorkflowStore(db)
    state = SessionState(session_id="s1", tenant_id="school-a")
    first = store.ensure(state)
    assert first["total"] == 10
    assert first["current_step"]["step_id"] == "self_exploration"
    state.profile.evidence_text = "我参与过社区调研"
    state.profile.target_job = "业务分析"
    second = store.sync_from_state(state, source_type="profile")
    assert second["completed"] >= 3
    # Explicit completion is persisted and not lost if the legacy snapshot no longer implies it.
    store.mark_completed("s1", "ppt", tenant_id="school-a", completed_by="teacher", source_type="manual")
    state.profile.target_job = ""
    later = store.sync_from_state(state, source_type="state_sync")
    ppt = next(x for x in later["steps"] if x["step_id"] == "ppt")
    assert ppt["status"] == "completed"
    assert ppt["completed_by"] == "teacher"


def test_evidence_graph_traces_artifact_review_feedback_and_revision(tmp_path: Path):
    db = str(tmp_path / "graph.db")
    run_migrations(db)
    evidence = EvidenceStore(db)
    artifacts = ArtifactStore(db)
    graph = EvidenceGraphStore(db)
    item = evidence.add(
        "s1", "student_chat", "学生对话", "我参与用户需求调研并完成12次访谈。",
        tenant_id="school-a",
    )
    v1 = artifacts.create_version(
        "s1", "career_report", "报告", "我参与用户需求调研并完成12次访谈。",
        tenant_id="school-a",
    )
    traced = graph.trace_artifact_version(
        tenant_id="school-a", session_id="s1", artifact_id=v1["artifact_id"], version_id=v1["version_id"],
        content=v1["content"], evidence_items=[item],
    )
    assert traced["claims"] >= 1 and traced["evidence_links"] >= 1
    review = graph.record_review(
        tenant_id="school-a", session_id="s1", artifact_id=v1["artifact_id"], version_id=v1["version_id"],
        report={"total_score": 76, "fatal_issues": [], "structural_issues": ["岗位证据不足"], "revision_priority": ["补充岗位调研"]},
    )
    graph.record_feedback(
        tenant_id="school-a", session_id="s1", feedback_id="FB-1", content="补充岗位调研证据", version_id=v1["version_id"],
    )
    v2 = artifacts.create_version("s1", "career_report_revision", "报告 · 修订版", "我参与用户需求调研并完成12次访谈，并补充目标机会调研。", tenant_id="school-a")
    graph.trace_artifact_version(
        tenant_id="school-a", session_id="s1", artifact_id=v2["artifact_id"], version_id=v2["version_id"], content=v2["content"], evidence_items=[item],
    )
    graph.link_revision(
        tenant_id="school-a", session_id="s1", previous_version_id=v1["version_id"], new_version_id=v2["version_id"], review_id=review["review_id"], feedback_ids=["FB-1"],
    )
    trace = graph.artifact_trace(v1["artifact_id"], tenant_id="school-a")
    assert len(trace["versions"]) == 2
    assert any(e["relation"] == "supported_by" and e["to_id"] == item["evidence_id"] for e in trace["edges"])
    assert any(e["relation"] == "revises" for e in trace["edges"])
    assert any(e["relation"] == "responds_to" and e["to_id"] == review["review_id"] for e in trace["edges"])


def test_hybrid_rag_year_filter_and_breakdown(tmp_path: Path):
    db = str(tmp_path / "hybrid.db")
    run_migrations(db)
    store = KnowledgeStore(db)
    current = store.ingest(
        title="2026岗位准备官方标准", filename="2026.txt", mime_type="text/plain",
        text="岗位准备评估强调目标清晰度、能力证据与发展潜力。", category="competition_rule", authority="official", effective_year="2026", priority=95,
    )
    store.ingest(
        title="2024历史评估标准", filename="2024.txt", mime_type="text/plain",
        text="岗位准备评估强调目标清晰度。", category="competition_rule", authority="official", effective_year="2024", priority=100,
    )
    result = store.search_detailed("2026 岗位准备 能力证据", effective_year="2026", top_k=5)
    assert result["hits"]
    assert result["hits"][0].source_id == current["source_id"]
    assert result["retrieval"]["mode"] == "hybrid"
    assert result["breakdown"]
    assert all(x["effective_year"] in {"2026", ""} for x in result["breakdown"])


def test_phase4_migrations_applied(tmp_path: Path):
    db = str(tmp_path / "migrate.db")
    run_migrations(db)
    assert migration_status(db)["current"] >= 6
