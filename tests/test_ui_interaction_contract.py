from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).parents[1]
STATIC = ROOT / "app" / "static"


def _values(source: str, attribute: str) -> set[str]:
    return set(re.findall(rf'{re.escape(attribute)}="([^"]+)"', source))


def test_student_visible_navigation_has_handlers_and_real_api_bindings():
    html = (STATIC / "student.html").read_text(encoding="utf-8")
    script = (STATIC / "student-workspace.js").read_text(encoding="utf-8")
    expected = {
        "coach", "exploration", "positioning", "capabilities", "tasks",
        "artifacts", "review", "interview", "history",
    }
    assert _values(html, "data-student-view") == expected
    for view in expected:
        assert re.search(rf"\b{re.escape(view)}\s*:", script), view
    for control in (
        "studentNotifications", "studentAccount", "studentAvatar",
        "workspace/v1/evidence", "workspace/v1/tasks", "workspace/v1/artifacts",
        "domain/v1/capabilities", "domain/v1/recompute",
        "workspace/v1/ai/interview/evaluate", "auth/logout",
        "artifacts/${encodeURIComponent(item.id)}/versions",
        "/api/artifacts/${encodeURIComponent(item.id)}/diff",
        "/api/artifacts/${encodeURIComponent(item.id)}/restore/",
        "careerosRadarGradient", "#2B5BFF", "#00D4AA",
        "CareerStudentWorkspace", "careeros:student-sidebar-ready",
        "studentSidebarReady", "runView(item.dataset.studentView",
    ):
        assert control in script
    assert 'src="/static/student-workspace.js?v=1.6.2"' in html
    for view in expected - {"coach", "history"}:
        assert f"#workspace-{view}" in html or view in {"artifacts", "review", "interview"}


def test_teacher_visible_navigation_has_handlers_and_real_api_bindings():
    html = (STATIC / "teacher.html").read_text(encoding="utf-8")
    script = (STATIC / "teacher-workspace.js").read_text(encoding="utf-8")
    expected = {
        "overview", "users", "profiles", "artifacts", "paths", "agents",
        "reviews", "tasks", "analytics", "knowledge", "settings",
    }
    assert _values(html, "data-teacher-view") == expected
    for view in expected:
        assert re.search(rf"\b{re.escape(view)}\s*:", script), view
    for control in (
        "workspaceSelect", "teacherHelp", "teacherNotifications",
        "teacherAccount", "topAdvisorAvatar", "teacher/dashboard",
        "teacher/sessions", "workspace/v1/modules", "api/tasks", "auth/logout",
        "workspace/v1/ai/coach", "advisor_recommendation", "/api/review",
    ):
        assert control in html + script
    assert 'src="/static/teacher-workspace.js?' in html


def test_global_i18n_and_admin_configuration_contracts():
    i18n = (STATIC / "i18n.js").read_text(encoding="utf-8")
    admin_html = (STATIC / "admin.html").read_text(encoding="utf-8")
    extension = (STATIC / "admin-extension.js").read_text(encoding="utf-8")
    for page in ("index.html", "login.html", "student.html", "teacher.html", "admin.html"):
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
