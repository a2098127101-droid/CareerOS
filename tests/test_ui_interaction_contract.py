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
    ):
        assert control in script
    assert 'src="/static/student-workspace.js?' in html


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
    ):
        assert control in html + script
    assert 'src="/static/teacher-workspace.js?' in html


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
