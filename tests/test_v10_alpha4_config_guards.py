import os
import subprocess
import sys
from pathlib import Path


def _run_settings(env):
    code='from app.config import Settings; print("|".join(Settings().validate_runtime()))'
    e=os.environ.copy(); e.update(env)
    return subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=e,text=True,capture_output=True)


def test_non_demo_production_requires_distributed_runtime_and_private_storage():
    r=_run_settings({
        'APP_ENV':'production','DEMO_MODE':'false','AUTH_REQUIRED':'true','COOKIE_SECURE':'true',
        'APP_SECRET_KEY':'x'*40,'ALLOWED_ORIGINS':'https://example.com','REPOSITORY_BACKEND':'postgresql',
        'DATABASE_URL':'postgresql://u:p@db/careeros','RUNTIME_STATE_BACKEND':'memory',
        'BACKGROUND_JOB_BACKEND':'inprocess','STORAGE_PROVIDER':'local'
    })
    assert r.returncode==0
    assert 'RUNTIME_STATE_BACKEND=redis' in r.stdout
    assert 'BACKGROUND_JOB_BACKEND=redis' in r.stdout
    assert 'STORAGE_PROVIDER=s3' in r.stdout


def test_production_cookie_mutations_require_allowed_origin(tmp_path):
    code=r'''
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app,base_url='https://testserver')
r=c.post('/api/auth/login',json={'email':'root@example.com','password':'Strong-Test-Password-123!','role':'super_admin'},headers={'Origin':'https://client.example'})
assert r.status_code==200,r.text
bad=c.post('/api/admin/tenants',json={'tenant_id':'orgx','name':'Org X','tenant_type':'organization','product_preset':'career_development'})
assert bad.status_code==403,bad.text
good=c.post('/api/admin/tenants',json={'tenant_id':'orgx','name':'Org X','tenant_type':'organization','product_preset':'career_development'},headers={'Origin':'https://client.example'})
assert good.status_code==200,good.text
print('CSRF_ORIGIN_OK')
'''
    env=os.environ.copy()
    env.update({
      'APP_ENV':'production','DEMO_MODE':'true','AUTH_REQUIRED':'true','COOKIE_SECURE':'true',
      'APP_SECRET_KEY':'x'*40,'ALLOWED_ORIGINS':'https://client.example','APP_DB_PATH':str(tmp_path/'csrf.db'),
      'AUTO_SEED_DEMO_USERS':'false','BOOTSTRAP_TENANT_ID':'demo-org','BOOTSTRAP_TENANT_NAME':'Demo Organization',
      'BOOTSTRAP_SUPERADMIN_EMAIL':'root@example.com','BOOTSTRAP_SUPERADMIN_PASSWORD':'Strong-Test-Password-123!',
      'REPOSITORY_BACKEND':'sqlite','RUNTIME_STATE_BACKEND':'memory','BACKGROUND_JOB_BACKEND':'inprocess','STORAGE_PROVIDER':'local'
    })
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,text=True,capture_output=True,timeout=90)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'CSRF_ORIGIN_OK' in result.stdout
