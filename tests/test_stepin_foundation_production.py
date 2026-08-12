from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.foundation_progress import FoundationProgressService
from app.foundation_production import EXPLORATIONS, ProductionFoundationFacade
from app.migrations import run_migrations
from app.repositories.container import RepositoryContainer


def build_foundation(tmp_path: Path):
    db_path = str(tmp_path / "foundation.db")
    run_migrations(db_path)
    repos = RepositoryContainer.build_sqlite(
        db_path=db_path,
        app_secret_key="x" * 40,
        session_ttl_hours=24,
        embedding_gateway=EmbeddingGateway(EmbeddingConfig()),
    )
    repos.identity.ensure_tenant("school-a", "School A")
    session = repos.sessions.create(
        tenant_id="school-a", student_user_id="student-a", class_id="default", student_id="student-a"
    )
    service = ProductionFoundationFacade(
        FoundationProgressService(
            repository=repos.runtime_entities,
            evidence=repos.evidence,
            artifacts=repos.artifacts,
        )
    )
    return repos, session, service


VALID_ANSWERS = {
    "FND-01-order": {"order": ["refund", "meeting", "report", "folder"], "reason": "客户正在等回复，而且会议也有明确的最近截止时间。"},
    "FND-02-key-info": {"selected": ["deadline", "people", "format"]},
    "FND-03-group": {"mapping": {"m1": "要马上处理", "m2": "需要确认", "m3": "只是记录", "m4": "要马上处理", "m5": "需要确认", "m6": "只是记录"}},
    "FND-04-find-problem": {"selected": ["missing_phone", "duplicate"], "reason": "缺少电话会联系不到人，重复记录会让人数和后续处理出错。"},
    "FND-05-handoff": {"fields": {"done": "已经确认了24个人是否参加", "left": "还有6个人没有回复需要继续联系", "next": "先联系剩余6人并在截止前补全名单"}},
    "FND-06-revise": {"revised": "目前30人中已经确认24人，还有6人没有回复。名单必须在周四16:00前提交，下一步先逐一联系剩余6人并补全最终状态。", "changeReason": "补上了确认人数、剩余人数、明确截止时间和下一步动作。"},
    "FND-07-transfer": {"choice": "broken_link", "reason": "报名链接现在打不开，而且40个人今天中午前都要用，影响最直接。"},
    "FND-08-mini-project": {"keyFactIds": ["capacity", "poster", "deadline"], "decision": "先处理人数超过教室容量和旧教室号问题，同时按周三截止时间整理处理说明。", "handoff": "目前报名42人但教室只能容纳35人，海报仍是旧教室号，周三18:00前要交处理说明。下一步先确认新的场地或人数安排，再立即更新海报，并在截止前把处理结果整理成一页说明交给老师。"},
}


def complete_foundation(service, session):
    for task_id, answer in VALID_ANSWERS.items():
        result = service.complete_task(
            task_id,
            answer,
            tenant_id="school-a",
            owner_user_id="student-a",
            session_id=session.session_id,
            updated_by="student-a",
        )
        assert result["ok"] is True, result


def test_foundation_starts_before_specialization(tmp_path: Path):
    _, session, service = build_foundation(tmp_path)
    summary = service.summary(tenant_id="school-a", owner_user_id="student-a", session_id=session.session_id)
    assert summary["mode"] == "beginner"
    assert summary["currentTask"]["id"] == "FND-01-order"
    assert summary["professionalUnlocked"] is False
    assert len(summary["abilities"]) == 10


def test_foundation_requires_expression_and_three_distinct_explorations(tmp_path: Path):
    _, session, service = build_foundation(tmp_path)
    complete_foundation(service, session)
    summary = service.summary(tenant_id="school-a", owner_user_id="student-a", session_id=session.session_id)
    assert summary["foundationComplete"] is True
    assert summary["mode"] == "expression"
    assert summary["professionalUnlocked"] is False

    service.expression(
        "我先找出真正影响任务的重点，再根据截止时间和影响范围作判断。收到反馈后，我把数字、时间和下一步补清楚，最后换了新的材料自己再做一次。",
        tenant_id="school-a",
        owner_user_id="student-a",
        session_id=session.session_id,
        updated_by="student-a",
    )
    summary = service.summary(tenant_id="school-a", owner_user_id="student-a", session_id=session.session_id)
    assert summary["mode"] == "exploration"
    assert summary["professionalUnlocked"] is False
    assert summary["exploration"]["next"]["id"] == "information"

    answers = {
        "information": {"selected": ["deadline", "missing", "format"]},
        "judgment": {"choice": "link", "reason": "链接现在影响40个人今天中午前报名，应该先处理。"},
        "expression": {"text": "已经确认24人，还有6人没有回复，名单周四16:00前必须交。下一步先联系剩余6人，确认后补进最终名单，再在截止前提交。"},
    }
    for index, kind in enumerate(EXPLORATIONS, start=1):
        result = service.complete_exploration(
            kind,
            answers[kind],
            tenant_id="school-a",
            owner_user_id="student-a",
            session_id=session.session_id,
            updated_by="student-a",
        )
        assert result["ok"] is True
        summary = service.summary(tenant_id="school-a", owner_user_id="student-a", session_id=session.session_id)
        assert summary["exploration"]["completed"] == index
    assert summary["professionalUnlocked"] is True
    assert summary["mode"] == "professional_ready"


def test_foundation_creates_canonical_evidence_and_mini_project(tmp_path: Path):
    repos, session, service = build_foundation(tmp_path)
    complete_foundation(service, session)
    evidence = repos.evidence.list_session(session.session_id, tenant_id="school-a")
    artifacts = repos.artifacts.list_session(session.session_id, include_content=True, tenant_id="school-a")
    assert len(evidence) >= 8
    assert any(item.get("kind") == "foundation_project" for item in artifacts)
    summary = service.summary(tenant_id="school-a", owner_user_id="student-a", session_id=session.session_id)
    assert summary["miniProjects"]


def test_beginner_page_uses_plain_language_and_single_step_flow():
    root = Path(__file__).parents[1]
    page = (root / "app" / "static" / "foundation.html").read_text(encoding="utf-8")
    gate = (root / "app" / "foundation_registration.py").read_text(encoding="utf-8")
    assert "今天先做这一小步" in page
    assert "不需要先选岗位" in gate
    assert "Prioritization Board" not in page
    assert "Contextual Copilot" not in page
    assert "Evidence" not in page


def test_production_http_gate_and_unlock_flow(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app, auth_store, settings

# Demo compatibility remains available when the explicit Foundation demo gate is disabled.
legacy = TestClient(app)
assert legacy.post('/api/auth/login', json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'}).status_code == 200
# The subprocess explicitly enables Foundation in demo mode, so all participants use the new path here.

user = auth_store.ensure_user(
    email='foundation-student@local.test',
    password='Foundation-Test-123!',
    display_name='Foundation Student',
    tenant_id=settings.bootstrap_tenant_id,
    role='student',
)
try:
    auth_store.add_class_member(
        class_id='demo-default',
        tenant_id=settings.bootstrap_tenant_id,
        user_id=user['user_id'],
        role='student',
    )
except Exception:
    pass

c = TestClient(app)
r = c.post('/api/auth/login', json={'email':'foundation-student@local.test','password':'Foundation-Test-123!','role':'student'})
assert r.status_code == 200, r.text
assert c.get('/projects', follow_redirects=False).status_code == 302
assert c.get('/projects', follow_redirects=False).headers['location'] == '/static/foundation.html'
next_action = c.get('/api/v1/me/next-action')
assert next_action.status_code == 200, next_action.text
assert next_action.json()['next_action']['action'] == 'foundation'
assert c.get('/api/v1/project-templates').json()['locked'] is True
locked = c.post('/api/v1/projects', json={})
assert locked.status_code == 423, locked.text
assert locked.json()['detail']['code'] == 'foundation_locked'

answers = {
 'FND-01-order': {'order':['refund','meeting','report','folder'],'reason':'客户正在等回复，而且会议也有最近截止时间。'},
 'FND-02-key-info': {'selected':['deadline','people','format']},
 'FND-03-group': {'mapping':{'m1':'要马上处理','m2':'需要确认','m3':'只是记录','m4':'要马上处理','m5':'需要确认','m6':'只是记录'}},
 'FND-04-find-problem': {'selected':['missing_phone','duplicate'],'reason':'缺少电话无法联系，重复记录会让后续人数统计出错。'},
 'FND-05-handoff': {'fields':{'done':'已经确认24个人是否参加','left':'还有6个人没有回复需要继续联系','next':'先联系剩余6人并在截止前补全名单'}},
 'FND-06-revise': {'revised':'目前30人中已经确认24人，还有6人没有回复。名单必须在周四16:00前提交，下一步先逐一联系剩余6人并补全最终状态。','changeReason':'补上确认人数、剩余人数、截止时间和下一步动作。'},
 'FND-07-transfer': {'choice':'broken_link','reason':'报名链接影响40个人今天中午前报名，应该先处理。'},
 'FND-08-mini-project': {'keyFactIds':['capacity','poster','deadline'],'decision':'先处理人数超过容量和旧教室号问题，并按周三截止时间整理说明。','handoff':'目前报名42人但教室只能容纳35人，海报仍是旧教室号，周三18:00前要交处理说明。下一步先确认新的场地或人数安排，再立即更新海报，并在截止前把处理结果整理成一页说明交给老师。'},
}
for task_id, answer in answers.items():
    rr = c.post('/api/foundation/v1/tasks/'+task_id+'/complete', json={'answer':answer})
    assert rr.status_code == 200, (task_id, rr.text)
    assert rr.json()['ok'] is True, (task_id, rr.text)

rr = c.post('/api/foundation/v1/expression', json={'reflection':'我先找重点，再根据截止时间和影响范围判断。收到意见后补清楚数字、时间和下一步，并换材料再做。'})
assert rr.status_code == 200, rr.text
for kind, answer in [
 ('information', {'selected':['deadline','missing','format']}),
 ('judgment', {'choice':'link','reason':'链接影响40个人今天中午前报名，必须先恢复。'}),
 ('expression', {'text':'已经确认24人，还有6人没有回复，名单周四16:00前必须交。下一步先联系剩余6人，确认后补进最终名单，再在截止前提交。'}),
]:
    rr = c.post('/api/foundation/v1/explorations/'+kind+'/complete', json={'answer':answer})
    assert rr.status_code == 200, (kind, rr.text)
    assert rr.json()['ok'] is True, (kind, rr.text)

me = c.get('/api/foundation/v1/me')
assert me.status_code == 200, me.text
assert me.json()['professionalUnlocked'] is True
assert c.get('/projects', follow_redirects=False).status_code == 200
assert c.get('/api/v1/project-templates').status_code == 200
assert c.get('/api/v1/project-templates').json()['items']

teacher = TestClient(app)
assert teacher.post('/api/auth/login', json={'email':'teacher@demo.local','password':'CareerOS-Demo-123!','role':'teacher'}).status_code == 200
cohort = teacher.get('/api/foundation/v1/cohort')
assert cohort.status_code == 200, cohort.text
assert cohort.json()['count'] >= 1
assert any(item['professionalUnlocked'] for item in cohort.json()['items'])
print('FOUNDATION_PRODUCTION_OK')
'''
    env = os.environ.copy()
    env.update({
        "APP_DB_PATH": str(tmp_path / "foundation-api.db"),
        "DEMO_MODE": "true",
        "STEPIN_FOUNDATION_DEMO_GATE": "true",
        "AUTH_REQUIRED": "true",
        "AUTO_SEED_DEMO_USERS": "true",
        "APP_SECRET_KEY": "test-secret-123456789012345678901234567890",
        "APP_ENV": "development",
    })
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[1],
        env=env,
        text=True,
        capture_output=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "FOUNDATION_PRODUCTION_OK" in result.stdout
