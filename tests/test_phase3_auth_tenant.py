import json
import sqlite3
from pathlib import Path

import pytest

from app.auth_store import AuthStore, Principal
from app.authz import can_access_session
from app.artifact_store import ArtifactStore
from app.evidence_store import EvidenceStore, is_evidence_candidate
from app.migrations import migration_status, run_migrations
from app.models import SessionState
from app.store import SessionStore


def setup_identity(db: str):
    run_migrations(db)
    auth = AuthStore(db)
    auth.ensure_tenant("school-a", "School A")
    auth.ensure_tenant("school-b", "School B")
    a_student = auth.create_user(email="a@student.test", password="VerySafe-Password-A1!", display_name="A Student", tenant_id="school-a", role="student")
    a_teacher = auth.create_user(email="a@teacher.test", password="VerySafe-Password-A1!", display_name="A Teacher", tenant_id="school-a", role="teacher")
    b_teacher = auth.create_user(email="b@teacher.test", password="VerySafe-Password-B1!", display_name="B Teacher", tenant_id="school-b", role="teacher")
    cls_a = auth.create_class("school-a", "Class A")
    cls_b = auth.create_class("school-b", "Class B")
    auth.add_class_member(class_id=cls_a["class_id"], tenant_id="school-a", user_id=a_student["user_id"], role="student")
    auth.add_class_member(class_id=cls_a["class_id"], tenant_id="school-a", user_id=a_teacher["user_id"], role="teacher")
    auth.add_class_member(class_id=cls_b["class_id"], tenant_id="school-b", user_id=b_teacher["user_id"], role="teacher")
    return auth, a_student, a_teacher, b_teacher, cls_a, cls_b


def principal(user: dict, tenant: str, role: str) -> Principal:
    return Principal(user_id=user["user_id"], email=user["email"], display_name=user["display_name"], tenant_id=tenant, role=role)


def test_password_hash_and_session_auth(tmp_path: Path):
    db = str(tmp_path / "auth.db")
    auth, student, *_ = setup_identity(db)
    raw = sqlite3.connect(db).execute("SELECT password_hash FROM users WHERE user_id=?", (student["user_id"],)).fetchone()[0]
    assert raw != "VerySafe-Password-A1!"
    assert raw.startswith("$argon2")
    p, token = auth.authenticate("a@student.test", "VerySafe-Password-A1!", tenant_id="school-a", role="student")
    resolved = auth.resolve_session(token)
    assert resolved and resolved.user_id == p.user_id and resolved.role == "student"
    auth.revoke_session(token)
    assert auth.resolve_session(token) is None


def test_rbac_and_tenant_isolation(tmp_path: Path):
    db = str(tmp_path / "tenant.db")
    auth, student, teacher_a, teacher_b, cls_a, _ = setup_identity(db)
    state = SessionState(session_id="s1", tenant_id="school-a", class_id=cls_a["class_id"], student_user_id=student["user_id"])
    assert can_access_session(principal(student, "school-a", "student"), state, auth)
    assert can_access_session(principal(teacher_a, "school-a", "teacher"), state, auth)
    assert not can_access_session(principal(teacher_b, "school-b", "teacher"), state, auth)
    other_student = auth.create_user(email="other@student.test", password="VerySafe-Password-C1!", display_name="Other", tenant_id="school-a", role="student")
    assert not can_access_session(principal(other_student, "school-a", "student"), state, auth)


def test_session_store_filters_before_limit(tmp_path: Path):
    db = str(tmp_path / "sessions.db")
    run_migrations(db)
    store = SessionStore(db)
    for i in range(5):
        s = store.create(tenant_id="school-b", student_id=f"b{i}")
    target = store.create(tenant_id="school-a", student_id="a")
    rows = store.list(limit=1, tenant_id="school-a")
    assert len(rows) == 1
    assert rows[0][0].session_id == target.session_id


def test_evidence_candidate_filter_blocks_commands(tmp_path: Path):
    assert not is_evidence_candidate("帮我评分")
    assert not is_evidence_candidate("继续")
    assert is_evidence_candidate("我有跨团队调研经历，完成多轮访谈并整理了项目材料。")
    db = str(tmp_path / "evidence.db")
    store = EvidenceStore(db)
    assert store.add_chat_candidate("s1", "帮我生成初稿") is None
    item = store.add_chat_candidate("s1", "我参与过需求调研，负责完成12次访谈并整理材料。")
    assert item and item["evidence_id"].startswith("EVID-")


def test_artifact_revision_uses_single_version_chain(tmp_path: Path):
    db = str(tmp_path / "artifact.db")
    store = ArtifactStore(db)
    v1 = store.create_version("s1", "career_report", "职业规划书 · 初稿", "V1")
    v2 = store.create_version("s1", "career_report_revision", "职业规划书 · 修订版", "V2")
    assert v1["artifact_id"] == v2["artifact_id"]
    assert v1["version"] == 1 and v2["version"] == 2
    assert store.latest("s1", "career_report")["content"] == "V2"
    versions = store.list_versions(v1["artifact_id"], tenant_id="demo-org")
    assert [x["version"] for x in versions] == [2, 1]


def test_legacy_database_migration_is_non_destructive(tmp_path: Path):
    db = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db)
    payload = {"session_id": "legacy-s", "tenant_id": "legacy-school", "class_id": "legacy-class", "student_id": "legacy-s", "stage": "profile", "profile": {}}
    conn.execute("CREATE TABLE sessions(session_id TEXT PRIMARY KEY,payload TEXT NOT NULL,updated_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("INSERT INTO sessions(session_id,payload) VALUES(?,?)", ("legacy-s", json.dumps(payload)))
    conn.execute("""CREATE TABLE artifacts(artifact_id TEXT PRIMARY KEY,session_id TEXT NOT NULL,kind TEXT NOT NULL,title TEXT NOT NULL,version INTEGER NOT NULL,content TEXT NOT NULL,metadata_json TEXT NOT NULL DEFAULT '{}',evidence_links_json TEXT NOT NULL DEFAULT '[]',created_at DATETIME DEFAULT CURRENT_TIMESTAMP,UNIQUE(session_id,kind,version))""")
    conn.execute("INSERT INTO artifacts(artifact_id,session_id,kind,title,version,content) VALUES('OLD-1','legacy-s','career_report','报告',1,'legacy content')")
    conn.commit(); conn.close()
    applied = run_migrations(db)
    assert migration_status(db)["current"] >= 3
    conn = sqlite3.connect(db); conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT tenant_id,class_id,payload FROM sessions WHERE session_id='legacy-s'").fetchone()
    assert row["tenant_id"] == "legacy-school" and row["class_id"] == "legacy-class"
    migrated = conn.execute("SELECT COUNT(*) FROM artifact_versions").fetchone()[0]
    legacy = conn.execute("SELECT content FROM artifacts WHERE artifact_id='OLD-1'").fetchone()[0]
    assert migrated == 1 and legacy == "legacy content"
    conn.close()
