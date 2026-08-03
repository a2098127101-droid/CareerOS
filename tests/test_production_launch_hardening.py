from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.routers.projects import _next_action, calculate_usage_cost


ROOT = Path(__file__).parents[1]


def test_next_action_is_deterministic_from_required_answers_and_status():
    project = {
        "project_id": "PRJ-1",
        "session_id": "SES-1",
        "status": "collecting",
        "answers": {"Q-1": "产品经理"},
        "template": {
            "questions": [
                {"question_id": "Q-1", "required": True},
                {"question_id": "Q-2", "required": True},
                {"question_id": "Q-3", "required": False},
            ]
        },
    }
    action = _next_action(project)
    assert action["action"] == "complete_project_profile"
    assert action["missing_question_ids"] == ["Q-2"]

    project["answers"]["Q-2"] = "真实项目经历"
    project["status"] = "ready_to_generate"
    action = _next_action(project)
    assert action["action"] == "generate_artifact"
    assert "session_id=SES-1" in action["href"]
    assert "project_id=PRJ-1" in action["href"]


def test_usage_cost_never_treats_unknown_model_as_zero_cost():
    result = calculate_usage_cost(
        [
            {
                "provider_id": "provider-a",
                "model": "priced",
                "input_tokens": 1_000_000,
                "output_tokens": 500_000,
                "success": 1,
            },
            {
                "provider_id": "provider-b",
                "model": "unknown",
                "input_tokens": 100,
                "output_tokens": 100,
                "success": 1,
            },
        ],
        [
            {
                "provider_id": "provider-a",
                "model": "priced",
                "input_cost_per_million": 2.0,
                "output_cost_per_million": 6.0,
            }
        ],
    )
    assert result["estimated_cost_usd"] == 5.0
    assert result["priced_calls"] == 1
    assert result["unpriced_calls"] == 1
    assert result["recent"][1]["estimated_cost_usd"] is None


def test_production_compose_is_private_by_default_and_uses_separate_migration_role():
    compose = (ROOT / "deploy" / "docker-compose.production.yml").read_text(encoding="utf-8")
    assert "internal: true" in compose
    assert "NOBYPASSRLS" not in compose  # Role enforcement belongs in the PostgreSQL init script.
    assert "POSTGRES_APP_USER" in compose
    assert "migrate:" in compose
    assert "REPOSITORY_BACKEND: postgresql" in compose
    assert '"127.0.0.1:${MINIO_CONSOLE_PORT:-9001}:9001"' in compose
    assert '"5432:5432"' not in compose
    assert '"6379:6379"' not in compose
    role_script = (ROOT / "deploy" / "postgres" / "init-app-role.sh").read_text(encoding="utf-8")
    assert "NOBYPASSRLS" in role_script
    assert "NOSUPERUSER" in role_script


def test_task_first_frontends_bind_real_project_and_governance_apis():
    projects = (ROOT / "app" / "static" / "projects.html").read_text(encoding="utf-8")
    student = (ROOT / "app" / "static" / "student.html").read_text(encoding="utf-8")
    teacher = (ROOT / "app" / "static" / "teacher.html").read_text(encoding="utf-8")
    governance = (ROOT / "app" / "static" / "governance.html").read_text(encoding="utf-8")
    assert "/api/v1/me/next-action" in projects
    assert "production-workspaces.css" in projects
    assert "params.get('session_id')" in student
    assert "/milestone?milestone=" in student
    assert "/api/v1/advisor/operations" in teacher
    assert "/api/teacher/sessions/" in teacher
    assert "/api/v1/governance/ai-usage" in governance
    assert "/api/v1/governance/audit-events" in governance


def test_project_governance_api_business_path(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app

student = TestClient(app)
login = student.post('/api/auth/login', json={
    'email': 'student@demo.local',
    'password': 'CareerOS-Demo-123!',
    'role': 'student',
})
assert login.status_code == 200, login.text

template = student.get('/api/v1/project-templates').json()['items'][0]
created = student.post('/api/v1/projects', json={
    'template_version_id': template['current_version_id'],
    'name': 'Product Manager Project',
})
assert created.status_code == 201, created.text
project = created.json()
next_action = student.get('/api/v1/me/next-action')
assert next_action.status_code == 200
assert next_action.json()['next_action']['action'] == 'complete_project_profile'

form = student.get('/api/v1/projects/' + project['project_id'] + '/form').json()
answers = [
    {'question_id': question['question_id'], 'answer': 'verified input'}
    for question in form['questions']
    if question.get('required')
]
saved = student.put('/api/v1/projects/' + project['project_id'] + '/answers', json={'answers': answers})
assert saved.status_code == 200, saved.text
assert saved.json()['status'] == 'ready_to_generate'

generated = student.patch('/api/v1/projects/' + project['project_id'] + '/milestone?milestone=generated')
assert generated.status_code == 200, generated.text
assert generated.json()['project']['status'] == 'solution_generated'

teacher = TestClient(app)
assert teacher.post('/api/auth/login', json={
    'email': 'teacher@demo.local',
    'password': 'CareerOS-Demo-123!',
    'role': 'teacher',
}).status_code == 200
operations = teacher.get('/api/v1/advisor/operations')
assert operations.status_code == 200, operations.text
assert any(item['project_id'] == project['project_id'] for item in operations.json()['queue'])

admin = TestClient(app)
assert admin.post('/api/auth/login', json={
    'email': 'admin@demo.local',
    'password': 'CareerOS-Demo-123!',
    'role': 'school_admin',
}).status_code == 200
usage = admin.get('/api/v1/governance/ai-usage')
assert usage.status_code == 200, usage.text
assert usage.json()['pricing_source'] == 'configured_model_capabilities'
audit = admin.get('/api/v1/governance/audit-events')
assert audit.status_code == 200, audit.text
assert any(event['action'] == 'project_created' for event in audit.json()['events'])
print('PRODUCTION_LAUNCH_API_OK')
'''
    env = os.environ.copy()
    env.update(
        {
            "APP_DB_PATH": str(tmp_path / "production-launch.db"),
            "DEMO_MODE": "true",
            "AUTH_REQUIRED": "true",
            "AUTO_SEED_DEMO_USERS": "true",
            "APP_SECRET_KEY": "test-secret-123456789012345678901234567890",
            "APP_ENV": "development",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "PRODUCTION_LAUNCH_API_OK" in result.stdout
