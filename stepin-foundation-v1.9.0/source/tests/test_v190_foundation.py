from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(tmp_path: Path, code: str, *, auth_required: bool = False) -> str:
    env = os.environ.copy()
    env.update({
        "APP_DB_PATH": str(tmp_path / "foundation.db"),
        "APP_ENV": "test",
        "AUTH_REQUIRED": "true" if auth_required else "false",
        "AUTO_SEED_DEMO_USERS": "true",
        "APP_SECRET_KEY": "test-secret-123456789012345678901234567890",
    })
    p = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parents[1], env=env, text=True, capture_output=True, timeout=180)
    assert p.returncode == 0, p.stdout + "\n" + p.stderr
    return p.stdout


def test_foundation_is_beginner_first_and_profile_does_not_skip_it(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
sid=c.get('/api/workspace/v1/context').json()['session_id']
f=c.get('/api/foundation/v1/me').json()
assert f['mode']=='beginner' and f['completed']==0 and f['total']==8
assert f['currentTask']['id']=='FND-01-order'
assert 'expectedTop' not in f['currentTask']['data']
t=c.get(f'/api/sessions/{sid}/today-next').json()
assert t['primary']['id']=='foundation_task' and t['primary']['taskId']=='FND-01-order'
assert t['policy']=='single_next_action_v2_foundation'
assert t['flow'][0]['label']=='开始做' and t['flow'][-1]['label']=='讲出来'
r=c.post(f'/api/sessions/{sid}/profile/extract',json={'text':'我是社会工作专业硕士研究生，做过访谈和社区调研，目标岗位是用户研究，我负责过8名访谈对象的整理和分析。'})
assert r.status_code==200,r.text
t2=c.get(f'/api/sessions/{sid}/today-next').json()
assert t2['primary']['id']=='foundation_task'
print('FOUNDATION_ENTRY_OK')
''')
    assert 'FOUNDATION_ENTRY_OK' in out


def test_foundation_full_chain_scaffold_project_expression_and_aggregation(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app,evidence_store,foundation_progress,unified_runtime_store
c=TestClient(app)
sid=c.get('/api/workspace/v1/context').json()['session_id']
answers={
'FND-01-order':{'order':['refund','meeting','report','folder'],'reason':'客户正在等今天回复，会议也有明确的明天截止时间。'},
'FND-02-key-info':{'selected':['deadline','people','format']},
'FND-03-group':{'mapping':{'m1':'要马上处理','m2':'需要确认','m3':'只是记录','m4':'要马上处理','m5':'需要确认','m6':'只是记录'}},
'FND-04-find-problem':{'selected':['missing_phone','duplicate'],'reason':'缺少电话会联系不到人，重复记录会让人数算错。'},
'FND-05-handoff':{'fields':{'done':'已经确认24个人参加活动。','left':'还有6个人没有回复是否参加。','next':'今天先联系这6个人，周四16点前交最终名单。'}},
'FND-06-revise':{'revised':'现在30人中已经确认24人，还有6人没有回复。名单周四16:00前要交。下一步今天先逐个联系这6人，确认后更新最终名单。','changeReason':'补上了确认人数、剩余人数、截止时间和下一步动作。'},
'FND-07-transfer':{'choice':'broken_link','reason':'报名今天12点就截止，而且40个人都会被打不开的链接直接影响。'},
'FND-08-mini-project':{'keyFactIds':['capacity','poster','deadline'],'decision':'先修正海报的旧教室信息，同时确认42人超过35人容量后的安排，并在周三18点前形成说明。','handoff':'目前发现三件关键事情：报名42人超过教室35人的容量，海报仍是旧教室号，周三18点前要交处理说明。先确认是否换更大教室或限制人数，同时马上修改海报；确定方案后把人数安排和新教室信息写进一页说明。'}
}
h=c.post('/api/foundation/v1/tasks/FND-01-order/hint').json(); assert h['available'] and h['used']==1
for i,(tid,ans) in enumerate(answers.items(),1):
    d=c.post(f'/api/foundation/v1/tasks/{tid}/complete',json={'answer':ans}).json()
    assert d['ok'],(tid,d)
    assert d['state']['completed']==i,(tid,d['state'])
h7=c.post('/api/foundation/v1/tasks/FND-07-transfer/hint')
assert h7.status_code in {200,422}
f=c.get('/api/foundation/v1/me').json()
assert f['foundationComplete'] and not f['professionalUnlocked'] and len(f['miniProjects'])==1
assert f['miniProjects'][0].get('artifactId')
assert any(x['level'] in {'能自己做','换个场景也能做','能组合起来做'} for x in f['abilities'])
t=c.get(f'/api/sessions/{sid}/today-next').json(); assert t['primary']['id']=='foundation_expression'
e=c.post('/api/foundation/v1/expression',json={'reflection':'我以前会直接动手，现在会先看截止时间、谁在等、最后要交成什么样，再开始排顺序。'}).json()
assert e['ok'] and e['expression']['resume'] and e['expression']['interview90s'] and e['artifactId']
f_after=c.get('/api/foundation/v1/me').json(); assert f_after['professionalUnlocked']
t2=c.get(f'/api/sessions/{sid}/today-next').json(); assert t2['primary']['id']=='bridge_practice' and t2['primary']['bridgeTotal']==3
for n in (1,2):
    rid=f'BRIDGE-DUP-{n}'
    unified_runtime_store.upsert(tenant_id='demo-org',entity_type='practice_runs',entity_id=rid,owner_user_id='demo-local',updated_by='test',payload={'id':rid,'templateId':'data-quality','title':'data-quality','status':'completed','sessionId':sid,'verified':False})
tdup=c.get(f'/api/sessions/{sid}/today-next').json(); assert tdup['primary']['id']=='bridge_practice' and tdup['context']['foundation']['explorationCompleted']==1
for n,tid in enumerate(['community-needs','feature-priority'],1):
    rid=f'BRIDGE-{n}'
    unified_runtime_store.upsert(tenant_id='demo-org',entity_type='practice_runs',entity_id=rid,owner_user_id='demo-local',updated_by='test',payload={'id':rid,'templateId':tid,'title':tid,'status':'completed','sessionId':sid,'verified':False})
t3=c.get(f'/api/sessions/{sid}/today-next').json(); assert t3['context']['foundation']['careerPathsVisible'] and t3['primary']['id']=='start_practice'
evidence_store.add_structured(sid,title='后续练习 · 优先级判断',action='比较三个选项后确定先后顺序',capabilities=['优先级判断','判断'],tenant_id='demo-org',owner_user_id='demo-local')
evidence_store.add_structured(sid,title='后续练习 · 客户判断',action='比较线索后决定先跟进哪一个',capabilities=['线索比较','判断'],tenant_id='demo-org',owner_user_id='demo-local')
f2=foundation_progress.summary(tenant_id='demo-org',owner_user_id='demo-local',session_id=sid)
judge=[x for x in f2['abilities'] if x['id']=='judge'][0]
assert judge['laterPracticeCount']>=2 and judge['repeatedAcrossTasks']
arts=c.get(f'/api/sessions/{sid}/artifacts').json()['artifacts']
assert any(a.get('kind')=='foundation_project' for a in arts)
assert any(a.get('kind')=='practice_expression' for a in arts)
print('FOUNDATION_CHAIN_OK')
''')
    assert 'FOUNDATION_CHAIN_OK' in out


def test_active_professional_run_is_not_interrupted_by_foundation(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
sid=c.get('/api/workspace/v1/context').json()['session_id']
tid=c.get('/api/practice/v1/templates').json()['items'][0]['id']
r=c.post('/api/practice/v1/runs',params={'template_id':tid}).json()['run']
t=c.get(f'/api/sessions/{r["sessionId"]}/today-next').json()
assert t['primary']['id']=='continue_practice' and r['id'] in t['primary']['href']
print('LEGACY_ACTIVE_RUN_OK')
''')
    assert 'LEGACY_ACTIVE_RUN_OK' in out


def test_teacher_growth_view_uses_foundation_progress(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
r=c.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!'}); assert r.status_code==200,r.text
uid=c.get('/api/auth/me').json()['user']['user_id']
a={'order':['refund','meeting','report','folder'],'reason':'客户今天在等回复，所以先处理退款，再准备有明确截止时间的会议。'}
r=c.post('/api/foundation/v1/tasks/FND-01-order/complete',json={'answer':a}); assert r.status_code==200,r.text
c.post('/api/auth/logout')
r=c.post('/api/auth/login',json={'email':'teacher@demo.local','password':'CareerOS-Demo-123!'}); assert r.status_code==200,r.text
g=c.get('/api/foundation/v1/growth/'+uid); assert g.status_code==200,g.text
d=g.json(); assert d['timeline'] and d['summary']['completed']==1
print('TEACHER_GROWTH_OK')
''', auth_required=True)
    assert 'TEACHER_GROWTH_OK' in out


def test_foundation_ui_is_beginner_mode_not_job_picker():
    student=Path('app/static/student.html').read_text(encoding='utf-8')
    css=Path('app/static/interaction2.css').read_text(encoding='utf-8')
    teacher=Path('app/static/teacher.html').read_text(encoding='utf-8')
    assert '/api/foundation/v1/me' in student
    assert 'renderFoundation' in student and 'foundationTrackHtml' in student
    assert '开始做' in student and '跟着做' in student and '自己做' in student and '小项目' in student
    assert '卡住了，给一点提示' in student
    assert '.fnd-shell' in css and '.fnd-order-card' in css and '.fnd-expression' in css
    assert '/api/foundation/v1/growth/' in teacher and '最近是怎么进步的' in teacher


def test_authenticated_student_cannot_bypass_foundation_and_session_is_explicit(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app,store
c=TestClient(app)
r=c.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!'}); assert r.status_code==200,r.text
ctx=c.get('/api/workspace/v1/context').json(); sid=ctx['session_id']
f=c.get('/api/foundation/v1/me',params={'session_id':sid}); assert f.status_code==200,f.text
r=c.post('/api/practice/v1/runs',params={'template_id':'data-quality'}); assert r.status_code==423,r.text
assert r.json()['detail']['code']=='foundation_locked'
other=store.create(tenant_id='demo-org',student_user_id='other-user',class_id='default',student_id='other-user')
r=c.get('/api/foundation/v1/me',params={'session_id':other.session_id}); assert r.status_code==403,r.text
print('FOUNDATION_SERVER_GATE_OK')
''', auth_required=True)
    assert 'FOUNDATION_SERVER_GATE_OK' in out


def test_teacher_can_browse_foundation_cohort_without_waiting_for_triage(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
assert c.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!'}).status_code==200
uid=c.get('/api/auth/me').json()['user']['user_id'];sid=c.get('/api/workspace/v1/context').json()['session_id']
a={'order':['refund','meeting','report','folder'],'reason':'客户今天在等回复，所以先处理退款，再准备明天有截止时间的会议。'}
r=c.post('/api/foundation/v1/tasks/FND-01-order/complete',params={'session_id':sid},json={'answer':a}); assert r.status_code==200,r.text
c.post('/api/auth/logout')
assert c.post('/api/auth/login',json={'email':'teacher@demo.local','password':'CareerOS-Demo-123!'}).status_code==200
r=c.get('/api/foundation/v1/cohort'); assert r.status_code==200,r.text
items=r.json()['items']; row=next(x for x in items if x['userId']==uid)
assert row['completed']==1 and row['sessionId']==sid
r=c.get('/api/foundation/v1/growth/'+uid,params={'session_id':sid}); assert r.status_code==200,r.text
assert r.json()['summary']['completed']==1
print('FOUNDATION_COHORT_OK')
''', auth_required=True)
    assert 'FOUNDATION_COHORT_OK' in out
