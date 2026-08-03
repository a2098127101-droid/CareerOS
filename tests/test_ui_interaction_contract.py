from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
STATIC = ROOT / "app" / "static"


def test_student_workspace_is_project_first_and_bound_to_real_apis():
    html = (STATIC / "student.html").read_text(encoding="utf-8")
    projects = (STATIC / "projects.html").read_text(encoding="utf-8")
    for token in (
        "Project Copilot", "params.get('project_id')", "params.get('session_id')",
        "/api/chat", "/api/files/parse", "/milestone?milestone=",
        "currentArtifactText", "downloadArtifact", "completeProject",
    ):
        assert token in html
    for token in (
        "/api/v1/me/next-action", "/api/v1/project-templates",
        "/api/v1/projects", "保存并判断下一步", "只处理当前最重要的任务",
    ):
        assert token in projects
    # The contracted student flow is intentionally reduced; the old feature-catalogue
    # navigation must not be reintroduced as the primary workspace.
    assert "data-student-view" not in html
    assert "student-workspace.js" not in html


def test_teacher_workspace_is_an_intervention_queue_with_real_actions():
    html = (STATIC / "teacher.html").read_text(encoding="utf-8")
    for token in (
        "教师运营中心", "干预队列", "/api/v1/advisor/operations",
        "/api/teacher/dashboard", "/api/teacher/sessions/", "/api/tasks",
        "/feedback", "/note", "createReminder", "priorityClass",
    ):
        assert token in html
    assert "data-teacher-view" not in html
    assert "teacher-workspace.js" not in html


def test_global_i18n_and_admin_configuration_contracts():
    i18n = (STATIC / "i18n.js").read_text(encoding="utf-8")
    admin_html = (STATIC / "admin.html").read_text(encoding="utf-8")
    extension = (STATIC / "admin-extension.js").read_text(encoding="utf-8")
    for page in (
        "index.html", "login.html", "projects.html", "student.html",
        "teacher.html", "governance.html", "admin.html",
    ):
        html = (STATIC / page).read_text(encoding="utf-8")
        assert "/static/i18n.js" in html, page
    for token in ("careeros_locale", "globe-2", "MutationObserver", "careeros:localechange", "en-US"):
        assert token in i18n
    assert 'data-tab="templates"' in admin_html
    assert 'data-tab="access"' in admin_html
    for endpoint in (
        "/api/admin/templates/workflows", "/api/admin/templates/artifacts",
        "/api/admin/users", "/role", "/status",
    ):
        assert endpoint in extension
    assert "workspace-select" in extension


def test_workspace_module_contract_and_interaction_apis(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app

student = TestClient(app)
r = student.post("/api/auth/login", json={
    "email": "student@demo.local",
    "password": "CareerOS-Demo-123!",
    "role": "student",
})
assert r.status_code == 200, r.text
modules = student.get("/api/workspace/v1/modules")
assert modules.status_code == 200, modules.text
contract = {item["id"]: item for item in modules.json()["modules"]}
for name in ("coach", "exploration", "positioning", "capabilities", "tasks", "artifacts", "review", "interview"):
    assert contract[name]["enabled"] is True
assert contract["users"]["enabled"] is False

evidence = student.post("/api/workspace/v1/evidence", json={
    "title": "Contract Evidence",
    "action": "Completed a verified UI interaction test.",
    "proof": "",
    "capabilities": [],
    "verified": False,
})
assert evidence.status_code == 200, evidence.text
tasks = student.get("/api/workspace/v1/tasks")
assert tasks.status_code == 200, tasks.text
artifacts = student.get("/api/workspace/v1/artifacts")
assert artifacts.status_code == 200, artifacts.text
created = student.post("/api/workspace/v1/artifacts", json={
    "id": "UI-PLAN-1", "title": "UI Contract Plan", "type": "career_report",
    "content": "Evidence-grounded plan V1", "evidence_ids": [],
})
assert created.status_code == 200, created.text
updated = student.patch("/api/workspace/v1/artifacts/UI-PLAN-1", json={
    "id": "UI-PLAN-1", "title": "UI Contract Plan", "type": "career_report",
    "content": "Evidence-grounded plan V2", "evidence_ids": [], "expected_version": 1,
})
assert updated.status_code == 200, updated.text
versions = student.get("/api/workspace/v1/artifacts/UI-PLAN-1/versions")
assert versions.status_code == 200, versions.text
assert len(versions.json()["versions"]) == 2

english = student.post("/api/chat", json={
    "session_id": student.get("/api/workspace/v1/context").json()["session_id"],
    "message": "What should I do next?", "locale": "en-US",
})
assert english.status_code == 200, english.text
assert english.json()["reply"]

teacher = TestClient(app)
r = teacher.post("/api/auth/login", json={
    "email": "teacher@demo.local",
    "password": "CareerOS-Demo-123!",
    "role": "teacher",
})
assert r.status_code == 200, r.text
teacher_modules = teacher.get("/api/workspace/v1/modules")
assert teacher_modules.status_code == 200, teacher_modules.text
teacher_contract = {item["id"]: item for item in teacher_modules.json()["modules"]}
assert teacher_contract["users"]["enabled"] is True
assert teacher.get("/api/teacher/dashboard").status_code == 200
assert teacher.get("/api/tasks").status_code == 200
print("UI_CONTRACT_OK")
'''
    env = os.environ.copy()
    env.update({
        "APP_DB_PATH": str(tmp_path / "ui-contract.db"),
        "AGENT_DB_PATH": str(tmp_path / "ui-contract-agent.db"),
        "DEMO_MODE": "true",
        "AUTH_REQUIRED": "true",
        "AUTO_SEED_DEMO_USERS": "true",
        "APP_SECRET_KEY": "test-secret-123456789012345678901234567890",
        "APP_ENV": "development",
    })
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "UI_CONTRACT_OK" in result.stdout
