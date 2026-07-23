from pathlib import Path

from app.artifact_store import ArtifactStore
from app.collaboration_store import CollaborationStore
from app.evidence_store import EvidenceStore
from app.lifecycle import workflow_snapshot
from app.models import SessionState


def test_artifact_versioning_and_evidence_links(tmp_path: Path):
    db = str(tmp_path / "test.db")
    artifacts = ArtifactStore(db)
    evidence = EvidenceStore(db)
    evidence.add("s1", "chat", "学生对话", "我完成12次访谈并负责材料整理。")
    links = evidence.link_text("s1", "我完成12次访谈，并负责材料整理。")
    a1 = artifacts.create_version("s1", "career_report", "报告", "V1", evidence_links=links)
    a2 = artifacts.create_version("s1", "career_report", "报告", "V2", evidence_links=links)
    assert a1["version"] == 1
    assert a2["version"] == 2
    assert artifacts.latest("s1", "career_report")["content"] == "V2"
    assert links and links[0]["evidence_id"].startswith("EVID-")


def test_teacher_feedback_creates_task_flow(tmp_path: Path):
    store = CollaborationStore(str(tmp_path / "test.db"))
    feedback = store.add_feedback("s1", "补充岗位选择依据", teacher_name="Demo Advisor", priority="high")
    task = store.ensure_task("处理教师反馈", "teacher_feedback", session_id="s1", priority="high")
    same = store.ensure_task("处理教师反馈", "teacher_feedback", session_id="s1", priority="high")
    assert feedback["status"] == "open"
    assert task["task_id"] == same["task_id"]
    store.resolve_feedback(feedback["feedback_id"])
    assert store.list_feedback("s1")[0]["status"] == "resolved"


def test_ten_step_workflow_snapshot():
    state = SessionState(session_id="s1")
    snap = workflow_snapshot(state)
    assert snap["total"] == 10
    assert snap["current_step"]["id"] == "self_exploration"
    state.profile.evidence_text = "真实项目经历"
    state.profile.target_job = "业务分析"
    snap = workflow_snapshot(state)
    assert snap["completed"] >= 3
    assert snap["steps"][0]["status"] == "completed"

from app.job_store import JobStore


def test_structured_job_store(tmp_path: Path):
    store = JobStore(str(tmp_path / "jobs.db"))
    store.upsert({
        "title": "业务分析师", "company": "示例公司", "city": "北京", "industry": "互联网",
        "skills": "访谈,数据分析", "description": "负责用户访谈与研究洞察"
    })
    rows = store.search("业务分析", city="北京")
    assert len(rows) == 1
    assert "访谈" in rows[0]["skills"]
    assert store.stats()["total"] == 1
