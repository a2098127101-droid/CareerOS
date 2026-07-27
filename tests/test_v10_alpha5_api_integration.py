import os
import subprocess
import sys
from pathlib import Path


def test_alpha5_identity_privacy_and_model_governance_api(tmp_path: Path):
    code = r'''
from fastapi.testclient import TestClient
from app.main import app
from app import network_security
import hashlib,hmac,json

# The provider record is never called in this test. Pin DNS to a public documentation
# address so enterprise DNS interception cannot make the SSRF validator environment-dependent.
network_security.socket.getaddrinfo=lambda *args,**kwargs:[
    (network_security.socket.AF_INET,network_security.socket.SOCK_STREAM,6,"",("93.184.216.34",443))
]

admin=TestClient(app)
r=admin.post('/api/auth/login',json={'email':'admin@demo.local','password':'CareerOS-Demo-123!','role':'school_admin'})
assert r.status_code==200,r.text
checkout=admin.post('/api/admin/billing/checkout',json={'plan_id':'enterprise','success_url':'','cancel_url':''})
assert checkout.status_code==200,checkout.text
assert checkout.json()['checkout']['sandbox'] is True
assert checkout.json()['real_payment_created'] is False
payload={'event_id':'evt-api-1','type':'checkout.completed','data':{'tenant_id':'demo-org','plan_id':'enterprise','status':'paid'}}
body=json.dumps(payload,separators=(',',':')).encode()
sig=hmac.new(b'test-billing-secret',body,hashlib.sha256).hexdigest()
wh=admin.post('/api/billing/webhooks/mock',content=body,headers={'Content-Type':'application/json','X-CareerOS-Billing-Signature':sig})
assert wh.status_code==200,wh.text
assert wh.json()['sandbox'] is True and wh.json()['duplicate'] is False
wh2=admin.post('/api/billing/webhooks/mock',content=body,headers={'Content-Type':'application/json','X-CareerOS-Billing-Signature':sig})
assert wh2.status_code==200,wh2.text
assert wh2.json()['duplicate'] is True
inv=admin.post('/api/admin/invitations',json={'email':'invited@example.test','role':'participant','display_name':'Invited User','ttl_hours':24})
assert inv.status_code==200,inv.text
token=inv.json()['invitation']['token']
assert token

member=TestClient(app)
acc=member.post('/api/auth/invitations/accept',json={'token':token,'password':'Password-12345','display_name':'Invited User'})
assert acc.status_code==200,acc.text
uid=acc.json()['user']['user_id']
login=member.post('/api/auth/login',json={'email':'invited@example.test','password':'Password-12345','role':'participant'})
assert login.status_code==200,login.text
cons=member.post('/api/privacy/consents',json={'policy_version':'2026-01','purpose':'service','granted':True,'source':'ui'})
assert cons.status_code==200,cons.text
export=member.get('/api/privacy/export')
assert export.status_code==200,export.text
assert export.json()['identity']['email']=='invited@example.test'
dsr=member.post('/api/privacy/requests',json={'request_type':'delete','notes':'test request'})
assert dsr.status_code==200,dsr.text
assert dsr.json()['request']['status']=='pending'

status=admin.patch('/api/admin/users/'+uid+'/status',json={'status':'disabled'})
assert status.status_code==200,status.text
assert status.json()['user']['status']=='disabled'
admin.patch('/api/admin/users/'+uid+'/status',json={'status':'active'})
role=admin.patch('/api/admin/users/'+uid+'/role',json={'role':'advisor'})
assert role.status_code==200,role.text
assert role.json()['user']['memberships'][0]['canonical_role']=='advisor'

superc=TestClient(app)
assert superc.post('/api/auth/login',json={'email':'super@demo.local','password':'CareerOS-Demo-123!','role':'super_admin'}).status_code==200
p=superc.post('/api/admin/providers',json={'provider_id':'demo-cap','name':'Demo Capability Provider','kind':'openai_compatible','base_url':'https://example.invalid/v1','api_key':'fake-key','default_model':'demo-model','enabled':True,'timeout_seconds':30,'extra_headers':{}})
assert p.status_code==200,p.text
cap=superc.put('/api/admin/models/capabilities',json={'provider_id':'demo-cap','model':'demo-model','supports_streaming':True,'supports_json_schema':True,'supports_tools':False,'supports_vision':False,'supports_files':False,'context_window':64000,'max_output':8000,'reasoning_level':'medium','latency_class':'fast','input_cost_per_million':1.0,'output_cost_per_million':2.0,'metadata':{}})
assert cap.status_code==200,cap.text
rec=superc.post('/api/admin/models/recommend',json={'required_capabilities':['streaming','json_schema'],'min_context_window':32000,'prefer_latency':'fast'})
assert rec.status_code==200,rec.text
assert rec.json()['candidates'][0]['provider_id']=='demo-cap'
print('ALPHA5_API_OK')
'''
    env=os.environ.copy()
    env.update({
      'APP_DB_PATH':str(tmp_path/'alpha5.db'),'STORAGE_LOCAL_ROOT':str(tmp_path/'uploads'),
      'DEMO_MODE':'true','AUTH_REQUIRED':'true','AUTO_SEED_DEMO_USERS':'true',
      'APP_SECRET_KEY':'test-secret-123456789012345678901234567890','APP_ENV':'development',
      'RUNTIME_STATE_BACKEND':'memory','BACKGROUND_JOB_BACKEND':'inprocess','BILLING_WEBHOOK_SECRET':'test-billing-secret'
    })
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,text=True,capture_output=True,timeout=120)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'ALPHA5_API_OK' in result.stdout
