from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_real_foundation_and_teacher_events_enter_agent_trajectory(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app

student = TestClient(app)
assert student.post('/api/auth/login', json={
    'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'
}).status_code == 200
me = student.get('/api/auth/me').json()['user']
uid = me['user_id']
state = student.get('/api/learner-agent/v1/state')
assert state.status_code == 200, state.text
sid = state.json()['state']['session_id']
summary = student.get('/api/foundation/v1/me').json()
task_id = summary['currentTask']['id']

failed = student.post('/api/foundation/v1/tasks/'+task_id+'/complete', json={'answer':{}})
assert failed.status_code == 200, failed.text
assert failed.json()['ok'] is False
hint = student.post('/api/foundation/v1/tasks/'+task_id+'/hint')
assert hint.status_code == 200, hint.text

trajectory = student.get('/api/learner-agent/v1/trajectory')
assert trajectory.status_code == 200, trajectory.text
types = [row['event_type'] for row in trajectory.json()['items']]
assert 'task_failed' in types, types
assert 'hint_requested' in types, types
assert student.get('/api/learner-agent/v1/state').json()['state']['last_observation']['event_type'] == 'hint_requested'

teacher = TestClient(app)
assert teacher.post('/api/auth/login', json={
    'email':'teacher@demo.local','password':'CareerOS-Demo-123!','role':'teacher'
}).status_code == 200
feedback = teacher.post('/api/teacher/sessions/'+sid+'/feedback', json={
    'teacher_name':'Demo Advisor','content':'请把判断依据写清楚，再改一版。','priority':'high'
})
assert feedback.status_code == 200, feedback.text
staff_view = teacher.get('/api/learner-agent/v1/trajectory', params={'subject_user_id':uid,'session_id':sid})
assert staff_view.status_code == 200, staff_view.text
types = [row['event_type'] for row in staff_view.json()['items']]
assert 'teacher_feedback' in types, types
agent_state = teacher.get('/api/learner-agent/v1/state', params={'subject_user_id':uid,'session_id':sid}).json()['state']
assert agent_state['diagnosis'] == 'REVISION_PENDING'
print('REAL_TRAJECTORY_BRIDGE_OK')
'''
    env = os.environ.copy()
    env.update({
        'APP_DB_PATH': str(tmp_path / 'real-trajectory.db'),
        'DEMO_MODE': 'true',
        'STEPIN_FOUNDATION_DEMO_GATE': 'true',
        'AUTH_REQUIRED': 'true',
        'AUTO_SEED_DEMO_USERS': 'true',
        'APP_SECRET_KEY': 'test-secret-123456789012345678901234567890',
        'APP_ENV': 'development',
    })
    result = subprocess.run(
        [sys.executable, '-c', code], cwd=Path(__file__).parents[1], env=env,
        text=True, capture_output=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    assert 'REAL_TRAJECTORY_BRIDGE_OK' in result.stdout
