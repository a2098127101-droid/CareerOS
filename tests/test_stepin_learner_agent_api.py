from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_learner_agent_http_contract_is_callable_by_independent_client(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
login = client.post('/api/auth/login', json={
    'email': 'student@demo.local',
    'password': 'CareerOS-Demo-123!',
    'role': 'student',
})
assert login.status_code == 200, login.text

manifest = client.get('/api/learner-agent/v1/manifest')
assert manifest.status_code == 200, manifest.text
body = manifest.json()
assert body['agentId'] == 'stepin-learner'
assert body['stateful'] is True
assert body['version'] == '2.2.0'
assert 'Trajectory' in body['components'] and 'Calibration' in body['components']
assert len(body['tools']) == 8
assert not any('generate' in x['name'] for x in body['tools'])

step = client.post('/api/learner-agent/v1/step', json={
    'event_type': 'user_message',
    'message': '我不知道怎么开始',
    'answer': {},
    'task_result': {},
    'client_context': {'surface': 'external-test-client'},
    'use_model': False,
})
assert step.status_code == 200, step.text
result = step.json()
assert result['decision']['action'] == 'ASK'
assert result['decision']['diagnosis'] == 'TASK_MODEL'
assert result['decision']['evaluation']['safe'] is True
assert result['state']['agent_id'] == 'stepin-learner'

state = client.get('/api/learner-agent/v1/state')
assert state.status_code == 200, state.text
assert state.json()['state']['agent_id'] == 'stepin-learner'

memory = client.get('/api/learner-agent/v1/memory')
assert memory.status_code == 200, memory.text
assert len(memory.json()['memory']['events']) >= 2

trajectory = client.get('/api/learner-agent/v1/trajectory')
assert trajectory.status_code == 200, trajectory.text
assert len(trajectory.json()['items']) >= 2

decisions = client.get('/api/learner-agent/v1/decisions')
assert decisions.status_code == 200, decisions.text
assert decisions.json()['items'][-1]['action'] == 'ASK'

evaluation = client.post('/api/learner-agent/v1/evaluate', json={})
assert evaluation.status_code == 200, evaluation.text
assert evaluation.json()['aggregate']['decisions'] >= 1
assert evaluation.json()['aggregate']['directAnswerLeakageRate'] == 0.0
assert evaluation.json()['aggregate']['trajectoryEventCount'] >= 2
print('LEARNER_AGENT_HTTP_OK')
'''
    env = os.environ.copy()
    env.update({
        "APP_DB_PATH": str(tmp_path / "learner-agent-api.db"),
        "DEMO_MODE": "true",
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
    assert "LEARNER_AGENT_HTTP_OK" in result.stdout
