import os
import subprocess
import sys
from pathlib import Path


def test_alpha6_email_runtime_certification_and_controlled_delete_api(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app

admin=TestClient(app)
assert admin.post('/api/auth/login',json={'email':'admin@demo.local','password':'CareerOS-Demo-123!','role':'school_admin'}).status_code==200
inv=admin.post('/api/admin/invitations',json={'email':'delete-me@example.test','role':'participant','display_name':'Delete Me','ttl_hours':24})
assert inv.status_code==200,inv.text
payload=inv.json()
assert payload['delivery']['provider']=='console' and payload['delivery']['accepted'] is True
token=payload['invitation']['token']

userc=TestClient(app)
acc=userc.post('/api/auth/invitations/accept',json={'token':token,'password':'Password-12345','display_name':'Delete Me'})
assert acc.status_code==200,acc.text
uid=acc.json()['user']['user_id']
assert userc.post('/api/auth/login',json={'email':'delete-me@example.test','password':'Password-12345','role':'participant'}).status_code==200
session=userc.post('/api/sessions').json()
assert session['student_user_id']==uid
req=userc.post('/api/privacy/requests',json={'request_type':'delete','notes':'alpha6 integration'})
assert req.status_code==200,req.text
rid=req.json()['request']['request_id']
plan=admin.get('/api/admin/privacy/requests/'+rid+'/plan')
assert plan.status_code==200,plan.text
assert session['session_id'] in plan.json()['plan']['session_ids']
preview=admin.post('/api/admin/privacy/requests/'+rid+'/process?confirm=false')
assert preview.status_code==200 and preview.json()['executed'] is False
processed=admin.post('/api/admin/privacy/requests/'+rid+'/process?confirm=true')
assert processed.status_code==200,processed.text
assert processed.json()['executed'] is True
users=admin.get('/api/admin/users').json()['users']
assert all(x['user_id']!=uid for x in users)

cert=admin.get('/api/admin/system/runtime-certification')
assert cert.status_code==200
assert cert.json()['available'] is False
print('ALPHA6_API_OK')
'''
    env=os.environ.copy()
    env.update({
      'APP_DB_PATH':str(tmp_path/'alpha6.db'),'STORAGE_LOCAL_ROOT':str(tmp_path/'uploads'),
      'EMAIL_OUTBOX_PATH':str(tmp_path/'outbox.jsonl'),'EMAIL_PROVIDER':'console',
      'DEMO_MODE':'true','AUTH_REQUIRED':'true','AUTO_SEED_DEMO_USERS':'true',
      'APP_SECRET_KEY':'test-secret-123456789012345678901234567890','APP_ENV':'development',
      'RUNTIME_STATE_BACKEND':'memory','BACKGROUND_JOB_BACKEND':'inprocess','PRIVACY_DELETE_EXECUTOR_ENABLED':'true',
      'RUNTIME_CERTIFICATION_FILE':str(tmp_path/'runtime-cert.json')
    })
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,text=True,capture_output=True,timeout=120)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'ALPHA6_API_OK' in result.stdout
    assert 'delete-me@example.test' in (tmp_path/'outbox.jsonl').read_text(encoding='utf-8')
