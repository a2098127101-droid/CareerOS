import os
import subprocess
import sys
from pathlib import Path


def test_alpha3_evidence_verify_and_rag_eval_api(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app

student=TestClient(app)
assert student.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'}).status_code==200
s=student.post('/api/sessions').json(); sid=s['session_id']
student.post('/api/chat',json={'session_id':sid,'message':'I completed 12 structured interviews and summarized the findings for a development project.'})
r=student.post('/api/draft/generate',json={'session_id':sid,'document_type':'职业规划书','extra_instructions':''})
assert r.status_code==200,r.text
v=student.post('/api/sessions/'+sid+'/evidence-verify',json={'claim_ids':[]})
assert v.status_code==200,v.text
assert 'results' in v.json()

a=TestClient(app)
assert a.post('/api/auth/login',json={'email':'super@demo.local','password':'CareerOS-Demo-123!','role':'super_admin'}).status_code==200
src=a.post('/api/admin/knowledge/text',json={'title':'Official Guidance','text':'The 2026 official guidance requires documented evidence and a development plan.','category':'policy','authority':'official','effective_year':'2026','priority':100})
assert src.status_code==200,src.text
source_id=src.json()['source']['source_id']
ev=a.post('/api/admin/knowledge/evaluate',json={'cases':[{'query':'2026 documented evidence development plan','expected_source_id':source_id,'expected_authority':'official','expected_year':'2026','scope':'global'}]})
assert ev.status_code==200,ev.text
assert ev.json()['metrics']['recall_at_5']==1.0
print('ALPHA3_API_OK')
'''
    env=os.environ.copy()
    env.update({
      'APP_DB_PATH':str(tmp_path/'alpha3.db'),'DEMO_MODE':'true','AUTH_REQUIRED':'true','AUTO_SEED_DEMO_USERS':'true',
      'APP_SECRET_KEY':'test-secret-123456789012345678901234567890','APP_ENV':'development'
    })
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,text=True,capture_output=True,timeout=90)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'ALPHA3_API_OK' in result.stdout
