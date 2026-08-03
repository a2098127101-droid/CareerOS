from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def _run(tmp_path: Path, code: str, *, auth: bool = False, timeout: int = 120):
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


def test_v15_schema_and_seed(tmp_path: Path):
    from app.migrations import run_migrations, migration_status
    db = str(tmp_path / "schema.db")
    run_migrations(db)
    assert migration_status(db)["current"] == 23
    with sqlite3.connect(db) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required = {
            "domain_claims", "domain_claim_versions", "capabilities", "capability_versions",
            "claim_evidence_links", "claim_capability_links", "job_requirement_versions", "job_requirement_capability_links",
            "capability_assessments", "capability_assessment_evidence", "career_gaps",
            "career_gap_versions", "domain_audit_events",
        }
        assert required <= tables
        assert conn.execute("SELECT COUNT(*) FROM capabilities WHERE tenant_id='global'").fetchone()[0] >= 10


def test_v15_persisted_explainable_domain_api(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app, job_store
c=TestClient(app)
assert c.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'}).status_code==200
me=c.get('/api/auth/me').json()['user']; uid=me['user_id']
e=c.post('/api/workspace/v1/evidence',json={'id':'E-DOM','title':'用户研究项目','action':'完成20名用户访谈并使用Python分析数据','proof':'访谈纪要','capabilities':['用户研究','Python']})
assert e.status_code==200,e.text
assert e.json()['item']['verificationStatus']=='SELF_REPORTED'
a=c.post('/api/workspace/v1/artifacts',json={'id':'A-DOM','title':'简历','type':'resume','content':'完成20名用户访谈，使用Python分析数据并输出报告。','evidence_ids':['E-DOM']})
assert a.status_code==200,a.text
job=job_store.upsert({'job_id':'JOB-DOM','title':'用户研究与数据分析','company':'Demo','skills':['用户研究','Python','SQL'],'description':'负责用户访谈、需求分析、Python与SQL数据分析，输出研究报告','source':'test'},tenant_id='demo-org')
r=c.post('/api/domain/v1/recompute',json={'job_id':'JOB-DOM','reason':'test domain intelligence'})
assert r.status_code==200,r.text
data=r.json()
assert data['claims'] and data['capabilities'] and data['gaps']
assert all('assessment_version' in x for x in data['capabilities'])
assert any(x['potential_score'] >= x['verified_score'] for x in data['capabilities'])
assert all('explanation' in x for x in data['gaps'])
s=c.get('/api/domain/v1/snapshot?job_id=JOB-DOM'); assert s.status_code==200,s.text
snap=s.json()['data']; assert snap['claims'] and snap['capabilities'] and snap['requirements'] and snap['audit']
req_id=snap['requirements'][0]['requirement_id']; assert c.get('/api/domain/v1/requirements/'+req_id+'/versions').json()['items']
cap=snap['capabilities'][0]
ex=c.get('/api/domain/v1/capabilities/'+cap['capability_id']+'/explain'); assert ex.status_code==200,ex.text
expl=ex.json()['data']; assert expl['capability'] and expl['latest_assessment'] is not None and 'claims' in expl
versions=c.get('/api/domain/v1/capabilities/'+cap['capability_id']+'/versions').json()['items']; assert versions
print('DOMAIN_API_OK',len(snap['claims']),len(snap['capabilities']),len(snap['gaps']))
''', auth=True)
    assert "DOMAIN_API_OK" in out


def test_v15_verification_changes_verified_assessment_and_is_audited(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app, job_store
student=TestClient(app); advisor=TestClient(app)
assert student.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'}).status_code==200
user=student.get('/api/auth/me').json()['user']; uid=user['user_id']
assert student.post('/api/workspace/v1/evidence',json={'id':'E-V','title':'Python项目','action':'使用Python完成数据分析项目','proof':'项目报告','capabilities':['Python','数据分析']}).status_code==200
job_store.upsert({'job_id':'JOB-V','title':'数据分析师','skills':['Python','数据分析'],'description':'需要Python和数据分析能力','source':'test'},tenant_id='demo-org')
before=student.post('/api/domain/v1/recompute',json={'job_id':'JOB-V'}).json()['capabilities']
bv=max((x['verified_score'] for x in before),default=0)
assert advisor.post('/api/auth/login',json={'email':'teacher@demo.local','password':'CareerOS-Demo-123!','role':'teacher'}).status_code==200
v=advisor.post('/api/workspace/v1/evidence/E-V/verification?subject_user_id='+uid,json={'decision':'verified','reason':'reviewed source','confidence':0.95,'method':'human_review'})
assert v.status_code==200,v.text
after=student.post('/api/domain/v1/recompute',json={'job_id':'JOB-V'}).json()['capabilities']
av=max((x['verified_score'] for x in after),default=0)
assert av >= bv and av > 0
hist=advisor.get('/api/workspace/v1/evidence/E-V/verification-history?subject_user_id='+uid); assert hist.status_code==200,hist.text
assert hist.json()['items'][0]['new_status']=='VERIFIED'
audit=student.get('/api/domain/v1/audit?entity_type=capability_assessment').json()['items']; assert audit
print('TRUST_RECOMPUTE_OK',bv,av)
''', auth=True)
    assert "TRUST_RECOMPUTE_OK" in out


def test_v15_claim_and_gap_version_conflicts(tmp_path: Path):
    out = _run(tmp_path, r'''
from fastapi.testclient import TestClient
from app.main import app, job_store
c=TestClient(app)
assert c.post('/api/auth/login',json={'email':'student@demo.local','password':'CareerOS-Demo-123!','role':'student'}).status_code==200
assert c.post('/api/workspace/v1/evidence',json={'id':'E-C','title':'沟通','action':'完成项目汇报','proof':'','capabilities':['沟通表达']}).status_code==200
job_store.upsert({'job_id':'JOB-C','title':'项目助理','skills':['沟通','SQL'],'description':'需要沟通汇报和SQL能力','source':'test'},tenant_id='demo-org')
r=c.post('/api/domain/v1/recompute',json={'job_id':'JOB-C'}); assert r.status_code==200,r.text
claim=r.json()['claims'][0]
u=c.patch('/api/domain/v1/claims/'+claim['claim_id'],json={'claim_text':claim['claim_text']+'（修订）','claim_type':claim['claim_type'],'expected_version':1,'reason':'manual correction'})
assert u.status_code==200,u.text and u.json()['item']['version']==2
stale=c.patch('/api/domain/v1/claims/'+claim['claim_id'],json={'claim_text':'stale','claim_type':'experience','expected_version':1})
assert stale.status_code==409,stale.text
versions=c.get('/api/domain/v1/claims/'+claim['claim_id']+'/versions').json()['items']; assert len(versions)>=2
gaps=c.get('/api/domain/v1/gaps?job_id=JOB-C').json()['items']; assert gaps
g=gaps[0]
up=c.patch('/api/domain/v1/gaps/'+g['gap_id'],json={'status':'planned','expected_version':g['version'],'reason':'accepted plan'}); assert up.status_code==200,up.text
assert c.patch('/api/domain/v1/gaps/'+g['gap_id'],json={'status':'resolved','expected_version':g['version']}).status_code==409
assert len(c.get('/api/domain/v1/gaps/'+g['gap_id']+'/versions').json()['items'])>=2
print('DOMAIN_VERSION_OK')
''', auth=True)
    assert "DOMAIN_VERSION_OK" in out


def test_v15_postgres_domain_repository_contract_on_sqlalchemy_sqlite(tmp_path: Path):
    from app.core.database import BASELINE_METADATA, create_database_engine
    from app.repositories.postgres.domain_intelligence import PostgresDomainIntelligenceRepository
    engine = create_database_engine("", str(tmp_path / "pg-parity.db"))
    BASELINE_METADATA.create_all(engine)
    repo = PostgresDomainIntelligenceRepository(engine)
    cap = repo.ensure_custom_capability(tenant_id="org-a", name="Systems Thinking", actor_user_id="admin")
    claim = repo.upsert_claim(
        tenant_id="org-a", session_id="S-1", owner_user_id="U-1", source_type="manual",
        source_id="SRC-1", source_locator="0", claim_text="Designed a systems map for a service workflow",
        claim_type="experience", actor_user_id="U-1",
    )
    repo.replace_claim_capability_links(
        tenant_id="org-a", claim_id=claim["claim_id"], session_id="S-1", actor_user_id="U-1",
        links=[{"capability_id": cap["capability_id"], "relation": "indicates", "confidence": 0.8, "explanation": "manual contract test"}],
    )
    assessment = repo.save_assessment(
        tenant_id="org-a", session_id="S-1", owner_user_id="U-1", capability_id=cap["capability_id"],
        potential_score=70, verified_score=40, confidence=0.75,
        explanation={"formula": "test", "methodology": "v1.5"}, contributions=[], actor_user_id="system",
    )
    assert assessment["assessment_version"] == 1
    explained = repo.explain_capability(cap["capability_id"], tenant_id="org-a", session_id="S-1")
    assert explained["latest_assessment"]["potential_score"] == 70
    updated = repo.update_claim(
        tenant_id="org-a", session_id="S-1", owner_user_id="U-1", claim_id=claim["claim_id"],
        claim_text="Designed and validated a systems map", claim_type="experience", actor_user_id="U-1", expected_version=1,
    )
    assert updated["version"] == 2 and len(repo.claim_versions(claim["claim_id"], tenant_id="org-a")) == 2
    engine.dispose()
