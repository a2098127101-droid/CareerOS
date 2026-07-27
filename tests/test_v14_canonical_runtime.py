import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from app.unified_runtime_store import UnifiedRuntimeStore, RuntimeVersionConflict


def _run(tmp_path: Path, code: str, *, auth: bool = False, timeout: int = 90):
    env = os.environ.copy()
    env.update({
        "APP_DB_PATH": str(tmp_path / "app.db"),
        "DEMO_MODE": "true",
        "AUTH_REQUIRED": "true" if auth else "false",
        "AUTO_SEED_DEMO_USERS": "true",
        "APP_ENV": "development",
        "APP_SECRET_KEY": "test-secret-123456789012345678901234567890",
    })
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parents[1], env=env, text=True, capture_output=True, timeout=timeout)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    return result.stdout


def test_runtime_owner_is_part_of_identity_and_version_conflicts(tmp_path: Path):
    store = UnifiedRuntimeStore(str(tmp_path / "runtime.db"))
    a = store.upsert(tenant_id="t", owner_user_id="u1", entity_type="notifications", entity_id="SAME", payload={"id":"SAME","title":"A"})
    b = store.upsert(tenant_id="t", owner_user_id="u2", entity_type="notifications", entity_id="SAME", payload={"id":"SAME","title":"B"})
    assert a["title"] == "A" and b["title"] == "B"
    assert store.get(tenant_id="t", owner_user_id="u1", entity_type="notifications", entity_id="SAME")["title"] == "A"
    assert store.get(tenant_id="t", owner_user_id="u2", entity_type="notifications", entity_id="SAME")["title"] == "B"
    updated = store.upsert(tenant_id="t", owner_user_id="u1", entity_type="notifications", entity_id="SAME", payload={"id":"SAME","title":"A2"}, expected_version=a["_version"])
    assert updated["_version"] == a["_version"] + 1
    try:
        store.upsert(tenant_id="t", owner_user_id="u1", entity_type="notifications", entity_id="SAME", payload={"id":"SAME","title":"lost"}, expected_version=a["_version"])
    except RuntimeVersionConflict:
        pass
    else:
        raise AssertionError("stale update must conflict")


def test_runtime_snapshot_is_not_truncated_at_5000(tmp_path: Path):
    db = tmp_path / "runtime_many.db"
    store = UnifiedRuntimeStore(str(db))
    # Bulk seed directly to exercise list_all/state paging without paying 5001 transaction costs.
    with sqlite3.connect(db) as conn:
        conn.executemany(
            "INSERT INTO unified_runtime_entities(tenant_id,owner_user_id,entity_type,entity_id,payload_json,version,revision,updated_by) VALUES(?,?,?,?,?,1,?,?)",
            [("t","u","usage_events",f"E{i}",'{"value":%d}'%i,i+1,"seed") for i in range(5001)],
        )
        conn.execute("INSERT OR REPLACE INTO unified_runtime_revisions(tenant_id,revision) VALUES('t',5001)")
        conn.commit()
    assert len(store.list_all(tenant_id="t", owner_user_id="u", entity_type="usage_events")) == 5001
    assert len(store.snapshot(tenant_id="t", owner_user_id="u", entity_types=["usage_events"])["usage_events"]) == 5001


def test_workspace_canonical_crud_optimistic_lock_and_artifact_series(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
# Evidence canonical CRUD + optimistic lock.
r=c.post('/api/workspace/v1/evidence',json={'id':'E1','title':'Interview','action':'Conducted 20 interviews','proof':'report','capabilities':['用户访谈'],'verified':False})
assert r.status_code==200,r.text
e=r.json()['item']; assert e['id']=='E1' and e['_version']==1
r=c.patch('/api/workspace/v1/evidence/E1',json={'id':'E1','title':'Interview 2','action':'Conducted 21 interviews','proof':'report','capabilities':['用户访谈'],'verified':False,'expected_version':1})
assert r.status_code==200,r.text; assert r.json()['item']['_version']==2
stale=c.patch('/api/workspace/v1/evidence/E1',json={'id':'E1','title':'stale','action':'stale write','proof':'','capabilities':[],'verified':False,'expected_version':1})
assert stale.status_code==409,stale.text
# Two artifacts of same kind remain independent when caller supplies ids.
a1=c.post('/api/workspace/v1/artifacts',json={'id':'A1','title':'Resume A','type':'简历','content':'v1','evidence_ids':['E1']}); assert a1.status_code==200,a1.text
a2=c.post('/api/workspace/v1/artifacts',json={'id':'A2','title':'Resume B','type':'简历','content':'other','evidence_ids':[]}); assert a2.status_code==200,a2.text
assert a1.json()['item']['id']=='A1' and a2.json()['item']['id']=='A2'
up=c.patch('/api/workspace/v1/artifacts/A1',json={'id':'A1','title':'Resume A','type':'简历','content':'v2','evidence_ids':['E1'],'expected_version':1}); assert up.status_code==200,up.text
assert up.json()['item']['id']=='A1' and up.json()['item']['_version']==2
versions=c.get('/api/workspace/v1/artifacts/A1/versions').json()['versions']; assert len(versions)==2 and {x['version'] for x in versions}=={1,2}
arts=c.get('/api/workspace/v1/artifacts').json()['items']; assert {x['id'] for x in arts}=={'A1','A2'}
# Task edits persist title/payload and reject stale version.
t=c.post('/api/workspace/v1/tasks',json={'id':'T1','title':'Old','description':'d1','type':'gap','status':'todo','priority':'normal','origin_type':'gap','origin_id':'SQL'}); assert t.status_code==200,t.text
u=c.patch('/api/workspace/v1/tasks/T1',json={'id':'T1','title':'New title','description':'d2','type':'gap','status':'done','priority':'high','origin_type':'gap','origin_id':'SQL','expected_version':1}); assert u.status_code==200,u.text
item=u.json()['item']; assert item['title']=='New title' and item['description']=='d2' and item['status']=='done' and item['_version']==2
assert c.patch('/api/workspace/v1/tasks/T1',json={'id':'T1','title':'stale','description':'','type':'gap','status':'todo','priority':'normal','origin_type':'gap','origin_id':'SQL','expected_version':1}).status_code==409
# Task soft-delete is also optimistic-lock protected.
assert c.delete('/api/workspace/v1/tasks/T1?expected_version=1').status_code==409
delok=c.delete('/api/workspace/v1/tasks/T1?expected_version=2'); assert delok.status_code==200,delok.text
# Generic runtime contains no canonical business collections.
rt=c.get('/api/runtime/v2/state').json()['data']; assert 'evidence' not in rt and 'artifacts' not in rt and 'tasks' not in rt
print('CANONICAL_OK')
''')
    assert "CANONICAL_OK" in out


def test_advisor_requires_relationship_for_subject_access(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app, auth_store
# Create another student in demo tenant.
u=auth_store.ensure_user(email='student2@test.local',password='CareerOS-Student2-123!',display_name='Student 2',tenant_id='demo-org',role='student')
teacher=TestClient(app); assert teacher.post('/api/auth/login',json={'email':'teacher@demo.local','password':'CareerOS-Demo-123!','role':'teacher'}).status_code==200
# No shared class: forbidden.
r=teacher.get('/api/workspace/v1/bootstrap?subject_user_id='+u['user_id']); assert r.status_code==403,r.text
# Add explicit teacher/student relationship.
t=auth_store.find_user_by_email('teacher@demo.local'); cls=auth_store.create_class('demo-org','Cohort V14')
auth_store.add_class_member(class_id=cls['class_id'],tenant_id='demo-org',user_id=t['user_id'],role='teacher')
auth_store.add_class_member(class_id=cls['class_id'],tenant_id='demo-org',user_id=u['user_id'],role='student')
r=teacher.get('/api/workspace/v1/bootstrap?subject_user_id='+u['user_id']); assert r.status_code==200,r.text
assert r.json()['subject_user_id']==u['user_id']
print('RELATION_SCOPE_OK')
''', auth=True)
    assert "RELATION_SCOPE_OK" in out


def test_provider_ssrf_and_plaintext_secret_guards(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
# Auth disabled demo principal is sufficient only if endpoint role allows; use legacy admin token behavior through seeded super login.
# Enable auth login with seeded super by using app's demo account if endpoint rejects anonymous.
r=c.post('/api/auth/login',json={'email':'super@demo.local','password':'CareerOS-Demo-123!','role':'super_admin'})
base={'provider_id':'ssrf','name':'SSRF','kind':'custom_rest','base_url':'http://127.0.0.1:9999','default_model':'x','enabled':True,'auth_type':'none','extra_headers':{},'query_params':{}}
r=c.post('/api/admin/providers',json=base); assert r.status_code==400,r.text; assert r.json()['detail']['code']=='unsafe_provider_configuration'
secret={**base,'provider_id':'secret','base_url':'https://example.invalid/api','extra_headers':{'Authorization':'Bearer plain'}}
r=c.post('/api/admin/providers',json=secret); assert r.status_code==400,r.text
print('PROVIDER_GUARDS_OK')
''', auth=True)
    assert "PROVIDER_GUARDS_OK" in out


def test_ai_workspace_does_not_fabricate_score_without_route(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
coach=c.post('/api/workspace/v1/ai/coach',json={'message':'Help me assess my fit','mode':'coach'})
assert coach.status_code in (200,503),coach.text
if coach.status_code==503:
    assert coach.json()['detail']['code']=='ai_route_unavailable'
else:
    assert coach.json()['mode']=='model_gateway' and coach.json().get('provider_id')
r=c.post('/api/workspace/v1/ai/interview/evaluate',json={'question':'Why?','answer':'Because I completed a real project with evidence and validated the role.','target_job':'Analyst'})
assert r.status_code in (200,503),r.text
if r.status_code==503:
    assert r.json()['detail']['code']=='ai_route_unavailable'
else:
    assert r.json()['mode']=='model_gateway' and 'evaluation' in r.json()
print('NO_FAKE_AI_OK')
''')
    assert "NO_FAKE_AI_OK" in out


def test_ci_is_not_locked_to_132_tests_and_showcase_has_real_ai_paths():
    ci=Path('.github/workflows/ci.yml').read_text(encoding='utf-8')
    assert 'passed_tests == 132' not in ci
    assert 'locked 132-test matrix' not in ci
    html=Path('CareerOS_H5_Showcase.html').read_text(encoding='utf-8')
    assert '/api/workspace/v1/ai/coach' in html
    assert "'/api/chat'" not in html[html.find('class ApiAdapter'):html.find('class CanonicalEntityService')]
    assert '/api/workspace/v1/ai/interview/evaluate' in html
    assert '/api/workspace/v1/ai/ppt/review' in html
    assert 'Demo mode does not fabricate an AI score' in html
    assert 'full collection replacement removed in v1.4' not in html  # backend message should not be UI flow
