import os
import subprocess
import sys
from pathlib import Path


def test_phase4_workflow_graph_trace_and_hybrid_api(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app

student=TestClient(app)
assert student.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'}).status_code==200
s=student.post('/api/sessions').json(); sid=s['session_id']
# real fact becomes evidence and workflow progresses
student.post('/api/chat',json={'session_id':sid,'message':'我有跨团队调研经历，完成多轮访谈与材料整理，目标岗位是业务分析。'})
wf=student.get('/api/sessions/'+sid+'/workflow').json()
assert wf['total']==10 and wf['completed']>=3
# generate -> review -> revise creates traceable versions
r=student.post('/api/draft/generate',json={'session_id':sid,'document_type':'职业规划书','extra_instructions':''})
assert r.status_code==200,r.text
art=r.json()['artifact']; aid=art['artifact_id']
rv=student.post('/api/review',json={'session_id':sid})
assert rv.status_code==200,rv.text
assert rv.json()['review_trace']['review_id'].startswith('REV-')
rr=student.post('/api/revise',json={'session_id':sid})
assert rr.status_code==200,rr.text
trace=student.get('/api/artifacts/'+aid+'/trace')
assert trace.status_code==200,trace.text
body=trace.json()
assert len(body['versions'])>=2
assert any(e['relation']=='contains_claim' for e in body['edges'])
assert any(e['relation']=='revises' for e in body['edges'])
graph=student.get('/api/sessions/'+sid+'/evidence-graph').json()
assert graph['claims'] and graph['edges']

superc=TestClient(app)
assert superc.post('/api/auth/login',json={'email':'super@demo.local','password':'CareerOS-Demo-123!','role':'super_admin'}).status_code==200
for title,text,year,priority in [
 ('2026官方评估标准','2026岗位准备评估强调能力证据与目标清晰度。','2026',95),
 ('2024历史评估标准','岗位准备评估强调目标清晰度。','2024',100),
]:
    q={'title':title,'text':text,'category':'competition_rule','authority':'official','effective_year':year,'priority':priority}
    assert superc.post('/api/admin/knowledge/text',json=q).status_code==200
res=superc.post('/api/admin/knowledge/search',json={'query':'2026 岗位准备 能力证据','effective_year':'2026','top_k':5})
assert res.status_code==200,res.text
j=res.json(); assert j['hits'] and j['retrieval']['mode']=='hybrid' and j['breakdown']
assert all(x['effective_year'] in ('2026','') for x in j['breakdown'])
print('PHASE4_OK')
'''
    env=os.environ.copy()
    env.update({
      'APP_DB_PATH':str(tmp_path/'phase4.db'),'DEMO_MODE':'true','AUTH_REQUIRED':'true','AUTO_SEED_DEMO_USERS':'true',
      'APP_SECRET_KEY':'test-secret-123456789012345678901234567890','APP_ENV':'development'
    })
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,text=True,capture_output=True,timeout=90)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'PHASE4_OK' in result.stdout
