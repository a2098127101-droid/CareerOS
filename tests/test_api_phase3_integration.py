import os
import subprocess
import sys
from pathlib import Path


def test_api_auth_and_cross_tenant_isolation(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app, auth_store

student = TestClient(app)
assert student.get('/student', follow_redirects=False).status_code == 302
r = student.post('/api/auth/login', json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'})
assert r.status_code == 200, r.text
s = student.post('/api/sessions')
assert s.status_code == 200, s.text
sid = s.json()['session_id']
assert student.get('/api/sessions/'+sid).status_code == 200
assert student.get('/api/teacher/dashboard').status_code == 403

teacher = TestClient(app)
r = teacher.post('/api/auth/login', json={'email':'teacher@demo.local','password':'CareerOS-Demo-123!','role':'teacher'})
assert r.status_code == 200, r.text
assert teacher.get('/api/teacher/sessions/'+sid).status_code == 200

# Create a second tenant and teacher directly through the identity store to verify server-side isolation.
auth_store.ensure_tenant('school-b','School B')
b = auth_store.ensure_user(email='teacher-b@test.local', password='CareerOS-Test-B-123!', display_name='Teacher B', tenant_id='school-b', role='teacher')
cls = auth_store.create_class('school-b','B Class')
auth_store.add_class_member(class_id=cls['class_id'],tenant_id='school-b',user_id=b['user_id'],role='teacher')
other = TestClient(app)
r = other.post('/api/auth/login', json={'email':'teacher-b@test.local','password':'CareerOS-Test-B-123!','role':'teacher'})
assert r.status_code == 200, r.text
assert other.get('/api/teacher/sessions/'+sid).status_code == 403
assert other.get('/api/teacher/dashboard').json()['stats']['total_students'] == 0
print('OK')
'''
    env = os.environ.copy()
    env.update({
        'APP_DB_PATH': str(tmp_path / 'api.db'),
        'DEMO_MODE': 'true',
        'AUTH_REQUIRED': 'true',
        'AUTO_SEED_DEMO_USERS': 'true',
        'APP_SECRET_KEY': 'test-secret-123456789012345678901234567890',
        'APP_ENV': 'development',
    })
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parents[1], env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    assert 'OK' in result.stdout


def test_production_security_is_fail_closed_and_valid_config_starts(tmp_path: Path):
    root = Path(__file__).parents[1]
    bad_env = os.environ.copy()
    bad_env.update({
        'APP_ENV': 'production',
        'AUTH_REQUIRED': 'false',
        'APP_DB_PATH': str(tmp_path / 'bad-prod.db'),
        'AUTO_SEED_DEMO_USERS': 'false',
    })
    failed = subprocess.run(
        [sys.executable, '-c', 'import app.main'], cwd=root, env=bad_env,
        text=True, capture_output=True, timeout=60,
    )
    assert failed.returncode != 0
    assert 'Production security validation failed' in failed.stdout + failed.stderr

    good_env = os.environ.copy()
    good_env.update({
        'APP_ENV': 'production',
        'AUTH_REQUIRED': 'true',
        'COOKIE_SECURE': 'true',
        'APP_SECRET_KEY': '0123456789abcdef0123456789abcdef0123456789abcdef',
        'ALLOWED_ORIGINS': 'https://careeros.example.test',
        'APP_DB_PATH': str(tmp_path / 'good-prod.db'),
        'AUTO_SEED_DEMO_USERS': 'false',
        'DEMO_MODE': 'true',
    })
    code = r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
r=c.get('/api/health')
assert r.status_code == 200
body=r.json()
assert body['auth']['required'] is True
assert body['auth']['environment'] == 'production'
assert body['migrations']['current'] >= 3
print('PROD_OK')
'''
    started = subprocess.run(
        [sys.executable, '-c', code], cwd=root, env=good_env,
        text=True, capture_output=True, timeout=60,
    )
    assert started.returncode == 0, started.stdout + '\n' + started.stderr
    assert 'PROD_OK' in started.stdout


def test_artifact_idor_and_teacher_feedback_not_promoted_to_student_evidence(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app, auth_store

student = TestClient(app)
assert student.post('/api/auth/login', json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'}).status_code == 200
s = student.post('/api/sessions').json(); sid=s['session_id']
# Commands must not become student evidence.
student.post('/api/chat', json={'session_id':sid,'message':'帮我评分'})
assert student.get('/api/sessions/'+sid+'/evidence').json()['items'] == []
# A factual statement can become a candidate evidence item.
student.post('/api/chat', json={'session_id':sid,'message':'我有跨团队调研经历，完成多轮访谈并整理了项目材料。'})
assert len(student.get('/api/sessions/'+sid+'/evidence').json()['items']) >= 1

# Create an artifact through the normal writer path.
r=student.post('/api/draft/generate',json={'session_id':sid,'document_type':'职业规划书','extra_instructions':''})
assert r.status_code == 200, r.text
arts=student.get('/api/sessions/'+sid+'/artifacts').json()['artifacts']
assert arts
artifact_id=arts[0]['artifact_id']

teacher=TestClient(app)
assert teacher.post('/api/auth/login',json={'email':'teacher@demo.local','password':'CareerOS-Demo-123!','role':'teacher'}).status_code==200
before=len(student.get('/api/sessions/'+sid+'/evidence').json()['items'])
fb=teacher.post('/api/teacher/sessions/'+sid+'/feedback',json={'content':'请补充岗位选择依据，不要虚构经历。','priority':'high'})
assert fb.status_code==200, fb.text
after=len(student.get('/api/sessions/'+sid+'/evidence').json()['items'])
assert after == before  # guidance is not student evidence

# Cross-tenant object access must fail even when the attacker knows artifact_id.
auth_store.ensure_tenant('school-b','School B')
b=auth_store.ensure_user(email='teacher-b2@test.local',password='CareerOS-Test-B2-123!',display_name='Teacher B2',tenant_id='school-b',role='teacher')
cls=auth_store.create_class('school-b','B2 Class')
auth_store.add_class_member(class_id=cls['class_id'],tenant_id='school-b',user_id=b['user_id'],role='teacher')
other=TestClient(app)
assert other.post('/api/auth/login',json={'email':'teacher-b2@test.local','password':'CareerOS-Test-B2-123!','role':'teacher'}).status_code==200
assert other.get('/api/artifacts/'+artifact_id).status_code == 403
print('IDOR_OK')
'''
    env = os.environ.copy()
    env.update({
        'APP_DB_PATH': str(tmp_path / 'idor.db'),
        'DEMO_MODE': 'true',
        'AUTH_REQUIRED': 'true',
        'AUTO_SEED_DEMO_USERS': 'true',
        'APP_SECRET_KEY': 'test-secret-123456789012345678901234567890',
        'APP_ENV': 'development',
    })
    result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).parents[1], env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    assert 'IDOR_OK' in result.stdout
