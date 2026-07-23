from __future__ import annotations

from pathlib import Path

from app.artifact_templates import resolve_artifact_template
from app.evidence_graph import EvidenceGraphStore
from app.job_intelligence import JobIntelligenceService
from app.job_store import JobStore
from app.migrations import migration_status, run_migrations
from app.models import SessionState
from app.workflow_store import WorkflowStore


def _db(tmp_path: Path) -> str:
    path = str(tmp_path / "alpha7.db")
    run_migrations(path)
    return path


def test_store_modules_no_longer_own_table_ddl():
    root = Path(__file__).resolve().parents[1] / "app"
    names = [
        "knowledge.py", "artifact_store.py", "evidence_graph.py", "store.py", "workflow_store.py",
        "job_store.py", "evidence_store.py", "collaboration_store.py", "model_store.py", "commercial_store.py",
    ]
    for name in names:
        text = (root / name).read_text(encoding="utf-8")
        assert "CREATE TABLE IF NOT EXISTS" not in text, name


def test_preset_workflow_templates_change_runtime_shape(tmp_path: Path):
    store = WorkflowStore(_db(tmp_path))
    career = SessionState(session_id="S-career", tenant_id="T")
    service = SessionState(session_id="S-service", tenant_id="T")
    enterprise = SessionState(session_id="S-enterprise", tenant_id="T")
    assert store.ensure(career, preset_id="career_development")["total"] == 10
    assert store.ensure(service, preset_id="career_service")["total"] == 7
    ent = store.ensure(enterprise, preset_id="enterprise_talent")
    assert ent["total"] == 7
    assert ent["template_id"] == "enterprise_talent_v1"
    assert any(s["label"] == "能力画像" for s in ent["steps"])


def test_artifact_template_resolves_legacy_and_enterprise_types():
    assert resolve_artifact_template("简历", "career_development").kind == "resume"
    assert resolve_artifact_template("人才发展报告", "enterprise_talent").kind == "development_report"
    assert resolve_artifact_template("行动计划", "career_service").kind == "action_plan"


def test_job_intelligence_never_infers_required_skill_from_job_itself(tmp_path: Path):
    db = _db(tmp_path)
    jobs = JobStore(db)
    job = jobs.upsert({
        "title": "Data Analyst",
        "skills": ["SQL", "Python"],
        "description": "本科及以上学历；具备数据分析经验；熟悉SQL和Python",
    }, tenant_id="org-a")
    state = SessionState(session_id="S1", tenant_id="org-a")
    state.profile.skills = ["SQL"]
    state.profile.evidence_text = "使用SQL完成过结构化数据分析项目。"
    result = JobIntelligenceService(jobs).match(
        job_id=job["job_id"], tenant_id="org-a", profile=state.profile, evidence_items=[]
    )
    python_rows = [r for r in result["requirements"] if r["requirement"].lower() == "python"]
    assert python_rows and python_rows[0]["status"] == "MISSING"
    assert result["policy"].startswith("job requirements and participant capabilities")


def test_evidence_verification_history_records_ai_and_human_decisions(tmp_path: Path):
    graph = EvidenceGraphStore(_db(tmp_path))
    graph.trace_artifact_version(
        tenant_id="org-a", session_id="S1", artifact_id="A1", version_id="V1",
        content="完成了10次用户访谈。",
        evidence_items=[{"evidence_id": "E1", "content": "完成了10次用户访谈。", "source_label": "profile"}],
    )
    claim = graph.list_claims("S1", tenant_id="org-a")[0]
    graph.update_claim_verification(
        claim["claim_id"], tenant_id="org-a", status="SUPPORTED", confidence=.9,
        verified_by="ai", verifier_type="ai", reason="automated check", session_id="S1",
    )
    graph.update_claim_verification(
        claim["claim_id"], tenant_id="org-a", status="PARTIALLY_SUPPORTED", confidence=.75,
        verified_by="advisor-1", verifier_type="human", reason="scope overstated", session_id="S1",
    )
    history = graph.verification_history(claim["claim_id"], tenant_id="org-a")
    assert [x["verifier_type"] for x in history] == ["ai", "human"]
    assert history[-1]["previous_status"] == "SUPPORTED"
    assert history[-1]["new_status"] == "PARTIALLY_SUPPORTED"


def test_migration_15_is_current(tmp_path: Path):
    db = _db(tmp_path)
    status = migration_status(db)
    assert status["current"] >= 15
    assert status["latest"] >= 15


def test_alpha7_template_and_job_match_api(tmp_path: Path):
    import os, subprocess, sys
    code = r'''
from fastapi.testclient import TestClient
from app.main import app, job_store, store
client=TestClient(app)
assert client.get('/api/product/workflow-templates').status_code==200
assert client.get('/api/product/artifact-templates').status_code==200
s=client.post('/api/sessions').json(); sid=s['session_id']
state=store.get(sid); state.profile.skills=['SQL']; state.profile.evidence_text='使用SQL完成数据分析项目。'; store.save(state)
job=job_store.upsert({'title':'Data Analyst','skills':['SQL','Python'],'description':'熟悉SQL和Python'},tenant_id=state.tenant_id)
r=client.post('/api/jobs/'+job['job_id']+'/match',json={'session_id':sid})
assert r.status_code==200,r.text
data=r.json(); assert data['summary']['MISSING']>=1
assert any(x['requirement']=='Python' and x['status']=='MISSING' for x in data['requirements'])
print('ALPHA7_API_OK')
'''
    env=os.environ.copy(); env.update({
        'APP_DB_PATH':str(tmp_path/'api.db'),'DEMO_MODE':'true','AUTH_REQUIRED':'false',
        'AUTO_SEED_DEMO_USERS':'false','APP_ENV':'development','APP_SECRET_KEY':'alpha7-test-secret-123456789012345678901234567890',
    })
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,text=True,capture_output=True,timeout=60)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'ALPHA7_API_OK' in result.stdout


def test_privacy_and_commercial_routes_are_modularized_without_duplicates(tmp_path: Path):
    import os, subprocess, sys
    main_text = (Path(__file__).parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert '@app.get("/api/privacy/export")' not in main_text
    assert '@app.get("/api/admin/commercial/overview")' not in main_text
    code = r'''
from collections import Counter
from app.main import app
keys=[]
for r in app.routes:
    methods=tuple(sorted(getattr(r,'methods',[]) or []))
    keys.append((getattr(r,'path',''),methods))
counts=Counter(keys)
targets=['/api/privacy/export','/api/admin/privacy/requests','/api/admin/commercial/overview','/api/admin/analytics/summary','/api/billing/webhooks/{provider_id}']
for path in targets:
    matches=[(k,v) for k,v in counts.items() if k[0]==path]
    assert matches, path
    assert all(v==1 for _,v in matches), (path,matches)
print('ROUTER_MODULARIZATION_OK')
'''
    env=os.environ.copy(); env.update({
        'APP_DB_PATH':str(tmp_path/'routes.db'),'DEMO_MODE':'true','AUTH_REQUIRED':'false',
        'AUTO_SEED_DEMO_USERS':'false','APP_ENV':'development',
        'APP_SECRET_KEY':'alpha7-router-test-secret-123456789012345678901234567890',
    })
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,text=True,capture_output=True,timeout=60)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'ROUTER_MODULARIZATION_OK' in result.stdout
