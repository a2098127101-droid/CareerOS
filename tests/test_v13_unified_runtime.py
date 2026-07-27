import os
import subprocess
import sys
from pathlib import Path

from app.unified_runtime_store import UnifiedRuntimeStore


def test_unified_runtime_store_owner_scoped_replace(tmp_path: Path):
    store = UnifiedRuntimeStore(str(tmp_path / "runtime.db"))
    # Migration compatibility helper remains owner-scoped; same entity id can safely exist per owner.
    store.replace(tenant_id="t1", entity_type="notifications", owner_user_id="u1", scope_owner_user_id="u1", items=[{"id": "SAME", "title": "A"}])
    store.replace(tenant_id="t1", entity_type="notifications", owner_user_id="u2", scope_owner_user_id="u2", items=[{"id": "SAME", "title": "B"}])
    assert [x["title"] for x in store.list(tenant_id="t1", entity_type="notifications", owner_user_id="u1")] == ["A"]
    assert [x["title"] for x in store.list(tenant_id="t1", entity_type="notifications", owner_user_id="u2")] == ["B"]


def test_v13_legacy_runtime_is_compatibility_only_for_business_entities(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
assert c.get('/api/runtime/v1/state').status_code == 200
# v1.4 intentionally blocks canonical business truth from the generic runtime compatibility API.
assert c.put('/api/runtime/v1/state/evidence',json={'value':[{'id':'E1','title':'Interview','action':'Conducted interviews'}]}).status_code == 410
assert c.post('/api/runtime/v1/entities/tasks',json={'id':'T1','payload':{'id':'T1','title':'Close SQL gap','status':'todo'}}).status_code == 410
# Singleton/transient UI state remains compatible.
r=c.put('/api/runtime/v1/state/settings',json={'value':{'productName':'CareerOS','runtimeMode':'api'}})
assert r.status_code == 200, r.text
snap=c.get('/api/runtime/v1/state').json()['data']
assert snap['settings']['productName']=='CareerOS'
print('V13_COMPAT_OK')
'''
    env = os.environ.copy()
    env.update({"APP_DB_PATH": str(tmp_path / "api.db"), "DEMO_MODE": "true", "AUTH_REQUIRED": "false", "APP_ENV": "development", "APP_SECRET_KEY": "test-secret-123456789012345678901234567890"})
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parents[1], env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "V13_COMPAT_OK" in result.stdout


def test_v13_legacy_api_cannot_bulk_replace_student_business_data(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app, auth_store
student=TestClient(app)
assert student.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'}).status_code==200
created=student.post('/api/workspace/v1/evidence',json={'id':'EA','title':'A','action':'A action','proof':'','capabilities':[],'verified':False})
assert created.status_code==200, created.text
# Staff/admin compatibility runtime cannot replace canonical Evidence collections.
advisor=TestClient(app)
assert advisor.post('/api/auth/login',json={'email':'teacher@demo.local','password':'CareerOS-Demo-123!','role':'teacher'}).status_code==200
r=advisor.put('/api/runtime/v1/state/evidence',json={'value':[{'id':'BAD','title':'overwrite','action':'overwrite'}]})
assert r.status_code==410, r.text
assert [x['id'] for x in student.get('/api/workspace/v1/evidence').json()['items']]==['EA']
print('NO_BULK_OVERWRITE_OK')
'''
    env = os.environ.copy()
    env.update({"APP_DB_PATH": str(tmp_path / "isolation.db"), "DEMO_MODE": "true", "AUTH_REQUIRED": "true", "AUTO_SEED_DEMO_USERS": "true", "APP_ENV": "development", "APP_SECRET_KEY": "test-secret-123456789012345678901234567890"})
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parents[1], env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "NO_BULK_OVERWRITE_OK" in result.stdout


def test_showcase_v14_routes_business_state_through_canonical_services():
    html = Path("CareerOS_H5_Showcase.html").read_text(encoding="utf-8")
    required = [
        "V14_STATE_SCHEMA=4",
        "CANONICAL_KEYS",
        "class CanonicalEntityService",
        "window.CareerOSServices",
        "/api/workspace/v1/bootstrap",
        "/api/workspace/v1/evidence",
        "/api/workspace/v1/artifacts",
        "/api/workspace/v1/tasks",
        "/api/admin/knowledge/ingest",
        "/api/admin/jobs/ingest-csv",
        "ModelGateway",
        "Domain Intelligence Runtime v1.5",
    ]
    for marker in required:
        assert marker in html
    assert "Custom REST API" in html
    assert "full collection PUT" not in html.lower()
