from __future__ import annotations

import time
from pathlib import Path

from app.background_jobs import InProcessJobManager
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.evidence_verification import EvidenceVerificationService, STATUS_PARTIAL, STATUS_SUPPORTED
from app.migrations import migration_status, run_migrations
from app.repositories.container import RepositoryContainer
from app.template_registry import TemplateRegistry


def _db(tmp_path: Path) -> str:
    path = str(tmp_path / "alpha8.db")
    run_migrations(path)
    return path


def test_tenant_custom_workflow_template_becomes_runtime_default(tmp_path: Path):
    db = _db(tmp_path)
    gateway = EmbeddingGateway(EmbeddingConfig())
    repos = RepositoryContainer.build_sqlite(
        db_path=db, app_secret_key="x" * 40, session_ttl_hours=24, embedding_gateway=gateway
    )
    created = repos.templates.create_workflow(
        tenant_id="org-a", preset_id="career_development", name="Compact Career Flow",
        steps=[
            {"step_id": "discover", "label": "发现", "required_evidence": True},
            {"step_id": "decide", "label": "决策"},
            {"step_id": "deliver", "label": "成果", "required_artifact": "portfolio"},
        ], created_by="admin-a",
    )
    repos.templates.activate_workflow(created["template_id"], tenant_id="org-a")
    state = repos.sessions.create(tenant_id="org-a", student_user_id="u1", class_id="g1", student_id="u1")
    snap = repos.workflows.ensure(state, preset_id="career_development")
    assert snap["template_id"] == created["template_id"]
    assert snap["total"] == 3
    assert [x["step_id"] for x in snap["steps"]] == ["discover", "decide", "deliver"]


def test_tenant_templates_are_isolated(tmp_path: Path):
    db = _db(tmp_path)
    from app.core.database import create_database_engine
    registry = TemplateRegistry(create_database_engine("", db))
    a = registry.create_workflow(
        tenant_id="org-a", preset_id="career_development", name="A",
        steps=[{"step_id": "a1", "label": "A1"}],
    )
    registry.activate_workflow(a["template_id"], tenant_id="org-a")
    assert registry.active_workflow(tenant_id="org-a", preset_id="career_development") is not None
    assert registry.active_workflow(tenant_id="org-b", preset_id="career_development") is None


def test_custom_artifact_template_resolution(tmp_path: Path):
    db = _db(tmp_path)
    from app.core.database import create_database_engine
    registry = TemplateRegistry(create_database_engine("", db))
    item = registry.create_artifact(
        tenant_id="org-a", kind="mobility_case", label="Internal Mobility Case",
        aliases=["internal move"], renderer="structured_report", review_rubric="mobility_v1",
        presets=["enterprise_talent"], schema={"sections": ["goal", "evidence", "gap"]},
    )
    registry.activate_artifact(item["template_id"], tenant_id="org-a")
    resolved = registry.resolve_artifact("internal move", tenant_id="org-a", preset_id="enterprise_talent")
    assert resolved and resolved["kind"] == "mobility_case"
    assert registry.resolve_artifact("internal move", tenant_id="org-b", preset_id="enterprise_talent") is None


def test_background_job_idempotency_prevents_duplicate_execution():
    manager = InProcessJobManager(max_workers=1, max_attempts=1)
    calls = {"n": 0}

    def handler(payload, progress):
        calls["n"] += 1
        progress(50, "working")
        return {"value": payload["value"]}

    manager.register("demo", handler)
    first = manager.enqueue(name="demo", payload={"value": 1}, tenant_id="org-a", idempotency_key="same-request")
    second = manager.enqueue(name="demo", payload={"value": 999}, tenant_id="org-a", idempotency_key="same-request")
    assert first.job_id == second.job_id
    deadline = time.time() + 3
    while time.time() < deadline:
        row = manager.get(first.job_id, tenant_id="org-a")
        if row and row.status == "SUCCEEDED":
            break
        time.sleep(0.02)
    row = manager.get(first.job_id, tenant_id="org-a")
    assert row and row.status == "SUCCEEDED"
    assert calls["n"] == 1
    assert row.result == {"value": 1}


def test_high_risk_claim_requires_human_review_even_when_supported():
    verifier = EvidenceVerificationService(EmbeddingGateway(EmbeddingConfig()))
    result = verifier.verify(
        "完成了10次用户访谈。",
        [{"evidence_id": "E1", "content": "完成了10次用户访谈。", "source_label": "verified profile"}],
    )
    assert result.status == STATUS_SUPPORTED
    assert result.risk_level == "high"
    assert result.requires_human_review is True


def test_high_risk_claim_without_explicit_support_is_not_auto_supported():
    verifier = EvidenceVerificationService(EmbeddingGateway(EmbeddingConfig()))
    result = verifier.verify(
        "获得国家级证书。",
        [{"evidence_id": "E1", "content": "参加了相关培训课程。", "source_label": "profile"}],
    )
    assert result.status != STATUS_SUPPORTED
    assert result.risk_level == "high"
    assert result.requires_human_review is True


def test_migration_16_is_current(tmp_path: Path):
    db = _db(tmp_path)
    status = migration_status(db)
    assert status["current"] >= 16
    assert status["latest"] >= 16


def test_alpha8_template_api_and_runtime_integration(tmp_path: Path):
    import os, subprocess, sys
    code = r'''
from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
wf=client.post('/api/admin/templates/workflows',json={
  'preset_id':'career_development','name':'API Custom Flow','steps':[
    {'step_id':'discover','label':'Discover','required_evidence':True},
    {'step_id':'deliver','label':'Deliver','required_artifact':'portfolio'}
  ]
})
assert wf.status_code==200,wf.text
wid=wf.json()['template']['template_id']
assert client.post('/api/admin/templates/workflows/'+wid+'/activate').status_code==200
cfg=client.get('/api/product/config').json()
assert cfg['workflow_template']==wid,cfg
s=client.post('/api/sessions').json(); sid=s['session_id']
snap=client.get('/api/sessions/'+sid+'/workflow').json()
assert snap['template_id']==wid and snap['total']==2,snap
art=client.post('/api/admin/templates/artifacts',json={
  'kind':'custom_brief','label':'Custom Brief','aliases':['brief'],
  'renderer':'structured_text','review_rubric':'brief_v1','presets':['career_development'],
  'schema':{'sections':['goal','evidence']}
})
assert art.status_code==200,art.text
aid=art.json()['template']['template_id']
assert client.post('/api/admin/templates/artifacts/'+aid+'/activate').status_code==200
listed=client.get('/api/product/artifact-templates').json()['templates']
assert any(x.get('template_id')==aid and x.get('source')=='tenant' for x in listed)
print('ALPHA8_TEMPLATE_API_OK')
'''
    env=os.environ.copy(); env.update({
        'APP_DB_PATH':str(tmp_path/'api-alpha8.db'),'DEMO_MODE':'true','AUTH_REQUIRED':'false',
        'AUTO_SEED_DEMO_USERS':'false','APP_ENV':'development',
        'APP_SECRET_KEY':'alpha8-template-api-secret-123456789012345678901234567890',
    })
    result=subprocess.run([sys.executable,'-c',code],cwd=Path(__file__).parents[1],env=env,text=True,capture_output=True,timeout=60)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
    assert 'ALPHA8_TEMPLATE_API_OK' in result.stdout


def test_evidence_risk_metadata_persists_in_claim_and_history(tmp_path: Path):
    from app.evidence_graph import EvidenceGraphStore
    db = _db(tmp_path)
    graph = EvidenceGraphStore(db)
    graph.trace_artifact_version(
        tenant_id="org-a", session_id="S-risk", artifact_id="A-risk", version_id="V-risk",
        content="完成了10次用户访谈。",
        evidence_items=[{"evidence_id": "E-risk", "content": "完成了10次用户访谈。", "source_label": "profile"}],
    )
    claim = graph.list_claims("S-risk", tenant_id="org-a")[0]
    updated = graph.update_claim_verification(
        claim["claim_id"], tenant_id="org-a", status="SUPPORTED", confidence=.95,
        verified_by="ai", verifier_type="ai", reason="explicit numeric evidence",
        session_id="S-risk", risk_level="high", requires_human_review=True,
    )
    assert updated["risk_level"] == "high"
    assert int(updated["requires_human_review"]) == 1
    history = graph.verification_history(claim["claim_id"], tenant_id="org-a")
    assert history[-1]["risk_level"] == "high"
    assert int(history[-1]["requires_human_review"]) == 1
