import os
import subprocess
import sys
from pathlib import Path


def test_alpha4_private_file_sse_jobs_and_probes(tmp_path: Path):
    code = r'''
import time
from urllib.parse import urlsplit
from fastapi.testclient import TestClient
from app.main import app

c=TestClient(app)
assert c.get('/live').status_code==200
assert c.get('/ready').status_code==200
assert c.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'}).status_code==200
s=c.post('/api/sessions').json(); sid=s['session_id']
files={'file':('note.txt',b'generic evidence note','text/plain')}
r=c.post('/api/files/parse',data={'session_id':sid},files=files)
assert r.status_code==200,r.text
body=r.json(); oid=body['storage']['object_id']
assert body['security']['detected_type']=='text/plain'
a=c.get('/api/files/'+oid+'/access')
assert a.status_code==200,a.text
url=a.json()['access_url']; parsed=urlsplit(url)
d=c.get(parsed.path+'?'+parsed.query)
assert d.status_code==200,d.text
assert d.content==b'generic evidence note'
with c.stream('POST','/api/chat/stream',json={'session_id':sid,'message':'My target direction is product operations.'}) as stream:
    text=''.join(stream.iter_text())
assert 'event: status' in text and 'event: result' in text

admin=TestClient(app)
assert admin.post('/api/auth/login',json={'email':'admin@demo.local','password':'CareerOS-Demo-123!','role':'school_admin'}).status_code==200
j=admin.post('/api/admin/knowledge/reindex-async?only_missing=true')
assert j.status_code==200,j.text
jid=j.json()['job']['job_id']
for _ in range(100):
    st=admin.get('/api/runtime/jobs/'+jid)
    assert st.status_code==200,st.text
    if st.json()['job']['status'] in ('SUCCEEDED','FAILED'):
        break
    time.sleep(.02)
assert st.json()['job']['status']=='SUCCEEDED',st.text
metrics=admin.get('/api/admin/system/metrics')
assert metrics.status_code==200
assert 'metrics' in metrics.json()
print('ALPHA4_API_OK')
'''
    env=os.environ.copy()
    env.update({
      'APP_DB_PATH':str(tmp_path/'alpha4.db'),'STORAGE_LOCAL_ROOT':str(tmp_path/'uploads'),
      'DEMO_MODE':'true','AUTH_REQUIRED':'true','AUTO_SEED_DEMO_USERS':'true',
      'APP_SECRET_KEY':'test-secret-123456789012345678901234567890','APP_ENV':'development',
      'RUNTIME_STATE_BACKEND':'memory','BACKGROUND_JOB_BACKEND':'inprocess'
    })
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,text=True,capture_output=True,timeout=120)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'ALPHA4_API_OK' in result.stdout
