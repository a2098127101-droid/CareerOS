from __future__ import annotations

from types import SimpleNamespace

from app.capability_verification import CapabilityVerificationService
from app.real_work_sample import RealWorkSampleService
from app.scene_state import SceneStateService


class FakeRepository:
    def __init__(self):
        self.rows = {}

    def _key(self, tenant_id, entity_type, entity_id, owner_user_id):
        return tenant_id, entity_type, entity_id, owner_user_id

    def get(self, *, tenant_id, entity_type, entity_id, owner_user_id="", **_):
        key = self._key(tenant_id, entity_type, entity_id, owner_user_id)
        if key not in self.rows:
            raise KeyError(entity_id)
        return dict(self.rows[key])

    def upsert(self, *, tenant_id, entity_type, entity_id, owner_user_id="", payload, expected_version=None, **_):
        key = self._key(tenant_id, entity_type, entity_id, owner_user_id)
        current = self.rows.get(key)
        actual = int(current.get("_version") or 1) if current else None
        if expected_version is not None and expected_version != actual:
            raise AssertionError((expected_version, actual))
        row = dict(payload)
        row["id"] = entity_id
        row["_version"] = (actual + 1) if actual else 1
        self.rows[key] = row
        return dict(row)


class FakeFoundation:
    def __init__(self, ability_rows=None, complete=True):
        self.ability_rows = ability_rows or []
        self.complete = complete

    def summary(self, **_):
        return {
            "mode": "expression" if self.complete else "beginner",
            "foundationComplete": self.complete,
            "professionalUnlocked": False,
            "progress": 100 if self.complete else 25,
            "completed": 8 if self.complete else 2,
            "total": 8,
            "currentTask": None,
            "abilities": list(self.ability_rows),
        }


class FakeEvidence:
    def __init__(self):
        self.rows = []

    def add_structured(self, session_id, *, title, action, proof="", capabilities=None, verified=False, tenant_id, owner_user_id, **_):
        row = {
            "evidence_id": f"E-{len(self.rows)+1}",
            "session_id": session_id,
            "tenant_id": tenant_id,
            "owner_user_id": owner_user_id,
            "source_label": title,
            "content": action,
            "metadata": {"proof": proof, "capabilities": list(capabilities or [])},
            "verification_status": "VERIFIED" if verified else "SELF_REPORTED",
            "verified": int(verified),
            "verification_confidence": 1.0 if verified else 0.0,
        }
        self.rows.append(row)
        return dict(row)

    def list_session(self, session_id, limit=100, *, tenant_id=None):
        return [dict(row) for row in self.rows if row["session_id"] == session_id and (tenant_id is None or row["tenant_id"] == tenant_id)][:limit]


class FakeArtifacts:
    def __init__(self):
        self.rows = []

    def create_workspace_version(self, *, session_id, title, kind, content, evidence_ids, tenant_id, owner_user_id, artifact_id=None, **_):
        artifact_id = artifact_id or "ART-1"
        version = 1 + sum(1 for row in self.rows if row["artifact_id"] == artifact_id)
        row = {
            "artifact_id": artifact_id,
            "version_id": f"{artifact_id}-V{version}",
            "version": version,
            "title": title,
            "kind": kind,
            "session_id": session_id,
            "tenant_id": tenant_id,
            "owner_user_id": owner_user_id,
            "metadata": {"workspace_evidence_ids": list(evidence_ids)},
            "evidence_links": [{"evidence_id": x} for x in evidence_ids],
            "is_current": True,
            "created_at": f"2026-08-12T00:00:0{version}Z",
        }
        for old in self.rows:
            if old["artifact_id"] == artifact_id:
                old["is_current"] = False
        self.rows.append(row)
        return dict(row)

    def list_session(self, session_id, include_content=False, *, tenant_id=None, all_versions=True):
        return [dict(row) for row in self.rows if row["session_id"] == session_id and (tenant_id is None or row["tenant_id"] == tenant_id)]


class FakeProjects:
    def list_projects(self, *, tenant_id, owner_user_id, status=None):
        return [{
            "project_id": "PRJ-1",
            "name": "真实任务综合实践",
            "status": "collecting",
            "progress": {"percent": 25},
            "updated_at": "2026-08-12T00:00:00Z",
        }]


class FakeTrajectory:
    def __init__(self, rows):
        self.rows = rows

    def list_events(self, **_):
        return list(self.rows)

    def summary(self, **_):
        return {"events": len(self.rows), "lastEventId": self.rows[-1]["event_id"] if self.rows else ""}


class FakeCalibration:
    def analyze(self, **_):
        return {"eventCount": 0, "transferSuccessRate": 0.0}


class FakeAgentState:
    def model_dump(self, mode="json"):
        return {"agent_id": "stepin-learner", "protocol_version": "2.2", "diagnosis": "PROGRESS"}


class FakeLearnerAgent:
    def __init__(self, rows):
        self.trajectory = FakeTrajectory(rows)
        self.calibration = FakeCalibration()

    def get_state(self, **_):
        return FakeAgentState()


def ability(result, capability_id):
    return next(item for item in result["items"] if item["capabilityId"] == capability_id)


def test_capability_verification_progresses_only_from_server_evidence():
    verifier = CapabilityVerificationService()
    foundation = {
        "abilities": [{
            "id": "judge", "attempts": 1, "guided": 0, "independent": 1,
            "transfer": 0, "combined": 0, "laterPracticeCount": 0,
        }]
    }
    v1 = {
        "event_id": "TRJ-V1", "event_type": "work_sample_v1_submitted", "outcome": "neutral",
        "task_id": "RWS-001-support-triage:main", "payload": {"capabilityIds": ["judge"], "independent": True},
    }
    result = verifier.verify(foundation_summary=foundation, trajectory_events=[v1], evidence_items=[])
    assert ability(result, "judge")["verificationLevel"] == "signal"
    assert ability(result, "judge")["metrics"]["distinctTaskContexts"] == 1

    v2 = {
        "event_id": "TRJ-V2", "event_type": "work_sample_v2_submitted", "outcome": "success",
        "task_id": "RWS-001-support-triage:main", "payload": {"capabilityIds": ["judge"], "independent": True},
    }
    result = verifier.verify(foundation_summary=foundation, trajectory_events=[v1, v2], evidence_items=[])
    assert ability(result, "judge")["verificationLevel"] == "evidence"
    assert ability(result, "judge")["metrics"]["distinctTaskContexts"] == 2

    transfer = {
        "event_id": "TRJ-T", "event_type": "work_sample_transfer_completed", "outcome": "success",
        "task_id": "RWS-001-support-triage:transfer", "payload": {"capabilityIds": ["judge"], "independent": True},
    }
    result = verifier.verify(foundation_summary=foundation, trajectory_events=[v1, v2, transfer], evidence_items=[])
    assert ability(result, "judge")["verificationLevel"] == "evidence"
    assert ability(result, "judge")["requirements"]["canonicalVerifiedEvidence"] is False

    verified = {
        "evidence_id": "E-VERIFIED",
        "source_label": "人工核验工作样本",
        "metadata": {"capabilities": ["比较后作判断"]},
        "verification_status": "VERIFIED",
        "verified": 1,
    }
    result = verifier.verify(foundation_summary=foundation, trajectory_events=[v1, v2, transfer], evidence_items=[verified])
    row = ability(result, "judge")
    assert row["verificationLevel"] == "verified_evidence"
    assert row["clientMayPromote"] is False
    assert row["authority"] == "server"


def test_duplicate_evidence_versions_do_not_fake_multiple_task_contexts():
    verifier = CapabilityVerificationService()
    foundation = {
        "abilities": [{
            "id": "judge", "attempts": 0, "guided": 0, "independent": 0,
            "transfer": 0, "combined": 0, "laterPracticeCount": 2,
        }]
    }
    evidence = [
        {"evidence_id": "E-1", "source_label": "V1", "metadata": {"capabilities": ["比较后作判断"]}, "verification_status": "SELF_REPORTED"},
        {"evidence_id": "E-2", "source_label": "V2", "metadata": {"capabilities": ["比较后作判断"]}, "verification_status": "SELF_REPORTED"},
    ]
    result = verifier.verify(foundation_summary=foundation, trajectory_events=[], evidence_items=evidence)
    row = ability(result, "judge")
    assert row["metrics"]["distinctTaskContexts"] == 1
    assert row["verificationLevel"] == "signal"


def test_real_work_sample_runs_v1_feedback_v2_and_transfer_without_auto_verification():
    repository = FakeRepository()
    foundation = FakeFoundation(complete=True)
    evidence = FakeEvidence()
    artifacts = FakeArtifacts()
    events = []
    service = RealWorkSampleService(
        repository=repository,
        foundation=foundation,
        evidence=evidence,
        artifacts=artifacts,
        observation_sink=lambda **event: events.append(event),
    )
    context = {"tenant_id": "school", "owner_user_id": "student", "session_id": "session", "updated_by": "student"}
    started = service.start(**context)
    assert started["status"] == "working_v1"

    v1 = service.submit_v1(
        priority_ticket_ids=["T-201", "T-203"],
        handoff="当前先处理报名链接和支付状态异常。报名链接影响40名同学且12:00截止；支付异常客户已追问且今天要发货。下一步先升级链接故障，同时核对支付记录并同步主管。",
        work_notes="我主要比较最近截止时间、受影响范围和不及时处理的直接后果；支付截图只能作为线索，入账状态仍需要核对。",
        **context,
    )
    assert v1["ok"] is True
    assert v1["state"]["status"] == "revision_required"
    assert v1["feedback"]

    v2 = service.submit_v2(
        priority_ticket_ids=["T-203", "T-201"],
        handoff="风险一：报名链接已多人复现，影响40名报名者，12:00停止报名，先升级技术处理并把进展同步负责人。风险二：客户支付后订单仍未更新，今天要发货，下一步核对支付记录后再决定订单处理，不能把截图直接写成已入账。",
        work_notes="根据主管反馈，我把影响人数、明确截止时间、不确定信息和下一位可以直接执行的动作补进 V2，并调整了交接结构。",
        **context,
    )
    assert v2["ok"] is True
    assert v2["state"]["status"] == "transfer_ready"

    transfer = service.submit_transfer(
        priority_ticket_ids=["X-301", "X-302"],
        handoff="先升级批量订单队列，23笔订单已经停止推进且10:45前要恢复或升级；随后处理尚未出库的地址修改，11:30前仍有处理窗口。下一步先保留队列异常证据并交技术排查，同时把地址修改交给订单同事继续处理。",
        work_notes="新材料仍按截止时间、影响范围和不处理后果排序，没有沿用上一组材料的具体答案。",
        **context,
    )
    assert transfer["ok"] is True
    assert transfer["state"]["status"] == "completed"
    assert [row["verification_status"] for row in evidence.rows] == ["SELF_REPORTED", "SELF_REPORTED", "SELF_REPORTED"]
    assert [event["event_type"] for event in events][-3:] == ["work_sample_v1_submitted", "work_sample_v2_submitted", "work_sample_transfer_completed"]
    assert events[-3]["outcome"] == "neutral"


def test_scene_state_is_read_only_and_spatial_nodes_only_mirror_authoritative_state():
    ability_rows = [{
        "id": "judge", "name": "比较后作判断", "plain": "比较后再取舍", "attempts": 2,
        "guided": 0, "independent": 1, "transfer": 1, "combined": 0, "laterPracticeCount": 0,
    }]
    foundation = FakeFoundation(ability_rows=ability_rows, complete=True)
    evidence = FakeEvidence()
    evidence.add_structured(
        "session", title="已核验交接", action="交接结果", proof="teacher review",
        capabilities=["比较后作判断"], verified=True, tenant_id="school", owner_user_id="student",
    )
    artifacts = FakeArtifacts()
    artifacts.create_workspace_version(
        session_id="session", title="交接 V1", kind="real_work_sample", content="x",
        evidence_ids=["E-1"], tenant_id="school", owner_user_id="student",
    )
    trajectory = [{
        "event_id": "TRJ-1", "event_type": "transfer_completed", "outcome": "success",
        "task_id": "FND-07-transfer", "payload": {}, "occurred_at": "2026-08-12T00:00:00Z",
    }]
    work_samples = SimpleNamespace(public_state=lambda **_: {
        "id": "RWS-001-support-triage", "version": "1.0", "unlocked": True, "status": "ready",
        "definition": {"title": "高峰时段支持工单交接"}, "v1": {}, "supervisorFeedback": [], "v2": {},
        "transferSubmission": {}, "artifactId": "", "evidenceIds": [], "unlockReason": "", "authority": "server",
    })
    service = SceneStateService(
        foundation=foundation,
        learner_agent=FakeLearnerAgent(trajectory),
        projects=FakeProjects(),
        evidence=evidence,
        artifacts=artifacts,
        capability_verification=CapabilityVerificationService(),
        work_samples=work_samples,
    )
    scene = service.build(tenant_id="school", owner_user_id="student", session_id="session")
    assert scene["authority"]["readOnly"] is True
    assert scene["authority"]["clientMayPromoteCapability"] is False
    assert set(scene["authority"]["allowedClientEffects"]) == {"focus", "inspect", "filter", "camera", "animation"}
    capability_node = next(node for node in scene["spatial"]["nodes"] if node["id"] == "capability:judge")
    assert capability_node["readOnly"] is True
    assert capability_node["data"]["clientMayPromote"] is False
    assert capability_node["state"] == "verified_evidence"
