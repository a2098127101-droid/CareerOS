from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.foundation_abilities import TASK_BY_ID, public_task
from app.learner_agent.evaluation import LearnerAgentEvaluator
from app.learner_agent.models import AgentAction, AgentObservationRequest, AgentStepRequest
from app.learner_agent.runtime import LearnerAgentRuntime
from app.unified_runtime_store import RuntimeVersionConflict


class FakeRepository:
    def __init__(self):
        self.rows = {}
        self.revision = 0

    def _key(self, tenant_id, owner_user_id, entity_type, entity_id):
        return tenant_id, owner_user_id, entity_type, entity_id

    def get(self, *, tenant_id, entity_type, entity_id, owner_user_id=None, **_):
        key = self._key(tenant_id, owner_user_id or "", entity_type, entity_id)
        if key not in self.rows:
            raise KeyError(entity_id)
        return dict(self.rows[key])

    def upsert(self, *, tenant_id, entity_type, entity_id, owner_user_id="", payload, expected_version=None, **_):
        key = self._key(tenant_id, owner_user_id, entity_type, entity_id)
        current = self.rows.get(key)
        actual = int(current.get("_version") or 1) if current else None
        if expected_version is not None and expected_version != actual:
            raise RuntimeVersionConflict(entity_id, expected_version, actual)
        row = dict(payload)
        row["id"] = entity_id
        row["_version"] = (actual + 1) if actual else 1
        self.revision += 1
        row["_revision"] = self.revision
        row["_ownerUserId"] = owner_user_id
        self.rows[key] = row
        return dict(row)

    def list(self, *, tenant_id, entity_type, owner_user_id=None, limit=5000, include_deleted=False, offset=0, **_):
        rows = [
            dict(row) for (tenant, owner, kind, _), row in self.rows.items()
            if tenant == tenant_id and kind == entity_type and (owner_user_id is None or owner == owner_user_id)
        ]
        rows.sort(key=lambda row: (int(row.get("_revision") or 0), str(row.get("id") or "")))
        return rows[offset:offset + limit]

    def list_all(self, *, tenant_id, entity_type, owner_user_id=None, include_deleted=False, **_):
        return self.list(tenant_id=tenant_id, entity_type=entity_type, owner_user_id=owner_user_id, limit=5000, include_deleted=include_deleted)


class FakeFoundation:
    def __init__(self):
        self.task = public_task(TASK_BY_ID["FND-01-order"])
        self.hints = {}

    def summary(self, *, owner_user_id, **_):
        return {
            "ok": True,
            "mode": "beginner",
            "foundationComplete": False,
            "professionalUnlocked": False,
            "currentTask": dict(self.task),
            "abilities": [
                {
                    "id": "judge",
                    "name": "比较后作判断",
                    "attempts": 2,
                    "independent": 1,
                    "transfer": 0,
                    "combined": 0,
                    "average": 0.82,
                    "laterVerifiedCount": 0,
                }
            ],
        }

    def get_task(self, task_id, *, owner_user_id, **_):
        if task_id != self.task["id"]:
            raise KeyError(task_id)
        return {"task": dict(self.task), "hintsUsed": self.hints.get(owner_user_id, 0), "done": False}

    def hint(self, task_id, *, owner_user_id, **_):
        if task_id != self.task["id"]:
            raise KeyError(task_id)
        used = self.hints.get(owner_user_id, 0) + 1
        self.hints[owner_user_id] = used
        return {"ok": True, "available": True, "used": used, "budget": 2, "message": "先比较截止时间和不及时处理的影响范围。"}


class FakeCollaboration:
    def __init__(self):
        self.tasks = []
        self.feedback = []

    def list_feedback(self, session_id, *, tenant_id=None):
        return list(self.feedback)

    def list_tasks(self, tenant_id="demo-org", status=None, limit=200, *, session_id=None, owner_user_id=None):
        rows = [x for x in self.tasks if (session_id is None or x.get("session_id") == session_id)]
        if owner_user_id is not None:
            rows = [x for x in rows if x.get("owner_user_id") == owner_user_id]
        return rows[:limit]

    def ensure_task(self, title, task_type, session_id="", tenant_id="demo-org", priority="normal", source="system", payload=None, owner_user_id=""):
        for row in self.tasks:
            if row["task_type"] == task_type and row["session_id"] == session_id and row["status"] in {"todo", "doing"}:
                return row
        row = {
            "task_id": f"T-{len(self.tasks)+1}",
            "title": title,
            "task_type": task_type,
            "session_id": session_id,
            "tenant_id": tenant_id,
            "owner_user_id": owner_user_id,
            "priority": priority,
            "source": source,
            "payload": payload or {},
            "status": "todo",
        }
        self.tasks.append(row)
        return row


class LeakyGateway:
    async def complete(self, task, system, user, *, tenant_id="global"):
        return SimpleNamespace(
            text="正确答案是处理一笔退款，你直接选这个即可。",
            provider_id="fake",
            model="fake-model",
            latency_ms=1,
            total_tokens=20,
        )


class LeakyCareerAgents:
    def __init__(self):
        self.gateway = LeakyGateway()

    def is_task_enabled(self, task):
        return task == "coach"


def build_runtime(*, model=False):
    repository = FakeRepository()
    foundation = FakeFoundation()
    collaboration = FakeCollaboration()
    runtime = LearnerAgentRuntime(
        repository=repository,
        foundation=foundation,
        collaboration=collaboration,
        career_agents=LeakyCareerAgents() if model else None,
    )
    return runtime, repository, foundation, collaboration


def test_state_is_persistent_and_owner_scoped():
    runtime, repository, _, _ = build_runtime()
    first = runtime.get_state(tenant_id="school", owner_user_id="u1", session_id="s1")
    second = runtime.get_state(tenant_id="school", owner_user_id="u1", session_id="s1")
    other = runtime.get_state(tenant_id="school", owner_user_id="u2", session_id="s2")
    assert first.agent_id == "stepin-learner"
    assert second.capability_states["judge"].stage == "independent"
    assert second.capability_states["judge"].confidence > 0
    assert other.owner_user_id == "u2"
    owners = {key[1] for key in repository.rows if key[2] == "learner_agent_state"}
    assert owners == {"u1", "u2"}


def test_observe_updates_diagnosis_without_executing_tools():
    runtime, _, foundation, collaboration = build_runtime()
    result = runtime.observe(
        AgentObservationRequest(event_type="task_failed", task_result={"ok": False, "issues": ["再试一次"]}),
        tenant_id="school",
        owner_user_id="u1",
        session_id="s1",
        updated_by="u1",
    )
    assert result["diagnosis"] == "METHOD_GAP"
    assert result["state"]["failure_streak"] == 1
    assert foundation.hints.get("u1", 0) == 0
    assert collaboration.tasks == []


@pytest.mark.asyncio
async def test_execution_loop_uses_fading_support_then_human_escalation():
    runtime, _, foundation, collaboration = build_runtime()
    actions = []
    for _ in range(5):
        result = await runtime.step(
            AgentStepRequest(
                event_type="task_failed",
                task_result={"ok": False, "issues": ["还没有按同一标准完成"]},
                use_model=False,
            ),
            tenant_id="school",
            owner_user_id="u1",
            session_id="s1",
            updated_by="u1",
        )
        actions.append(result["decision"]["action"])
    assert actions == ["ASK", "HINT", "EXPLAIN", "REQUEST_EVIDENCE", "ESCALATE"]
    assert foundation.hints["u1"] == 1
    assert any(x["task_type"] == "learner_evidence_request" for x in collaboration.tasks)
    assert any(x["task_type"] == "learner_human_review" for x in collaboration.tasks)


def test_tool_contract_does_not_expose_final_answer_generation():
    runtime, _, _, _ = build_runtime()
    names = {row["name"] for row in runtime.tools.manifest()}
    assert names == {
        "read_foundation",
        "next_hint",
        "request_evidence",
        "create_revision_task",
        "verification_snapshot",
        "assign_transfer",
        "advance",
        "escalate_human",
    }
    assert not any("generate" in name or "answer" in name for name in names)


def test_evaluation_detects_direct_answer_leakage():
    evaluator = LearnerAgentEvaluator()
    leaked = evaluator.evaluate_output(
        action=AgentAction.HINT,
        output_text="正确答案是处理一笔退款。",
        task_id="FND-01-order",
    )
    safe = evaluator.evaluate_output(
        action=AgentAction.EXPLAIN,
        output_text="先比较截止时间、影响范围和不及时处理的后果，再用同一标准排序。",
        task_id="FND-01-order",
    )
    assert leaked["directAnswerLeak"] is True
    assert safe["safe"] is True


@pytest.mark.asyncio
async def test_model_is_language_layer_and_leaky_output_is_rejected():
    runtime, _, _, _ = build_runtime(model=True)
    result = await runtime.step(
        AgentStepRequest(message="我不知道怎么开始", use_model=True),
        tenant_id="school",
        owner_user_id="u1",
        session_id="s1",
        updated_by="u1",
    )
    assert result["decision"]["action"] == "ASK"
    assert result["decision"]["model"]["accepted"] is False
    assert "处理一笔退款" not in result["decision"]["response"]
    assert result["decision"]["evaluation"]["safe"] is True


@pytest.mark.asyncio
async def test_memory_and_evaluation_are_queryable_after_decision():
    runtime, _, _, _ = build_runtime()
    await runtime.step(
        AgentStepRequest(message="我先自己试试", use_model=False),
        tenant_id="school",
        owner_user_id="u1",
        session_id="s1",
        updated_by="u1",
    )
    decisions = runtime.memory.recent(
        tenant_id="school",
        owner_user_id="u1",
        session_id="s1",
        limit=20,
        kind="decision",
    )
    report = runtime.evaluation_report(tenant_id="school", owner_user_id="u1", session_id="s1")
    assert len(decisions) == 1
    assert decisions[0]["action"] == "ASK"
    assert report["decisions"] == 1
    assert report["directAnswerLeakageRate"] == 0.0
    assert report["agentHealthy"] is True


def test_server_event_becomes_persistent_trajectory_observation():
    runtime, _, _, _ = build_runtime()
    result = runtime.ingest_server_event(
        event_type="task_failed",
        source="foundation",
        tenant_id="school",
        owner_user_id="u1",
        session_id="s1",
        actor_user_id="u1",
        task_id="FND-01-order",
        outcome="failure",
        payload={"task_result": {"ok": False, "issues": ["还没有按同一标准完成"]}},
    )
    assert result["observation"]["diagnosis"] == "METHOD_GAP"
    rows = runtime.trajectory.list_events(tenant_id="school", owner_user_id="u1", session_id="s1")
    assert len(rows) == 1
    assert rows[0]["event_type"] == "task_failed"
    state = runtime.get_state(tenant_id="school", owner_user_id="u1", session_id="s1")
    assert state.trajectory_event_count == 1
    assert state.last_trajectory_event_id == rows[0]["event_id"]


def test_trajectory_is_strictly_tenant_and_owner_scoped():
    runtime, _, _, _ = build_runtime()
    for owner in ("u1", "u2"):
        runtime.ingest_server_event(
            event_type="answer_saved", source="foundation", tenant_id="school", owner_user_id=owner,
            session_id=f"s-{owner}", actor_user_id=owner, task_id="FND-01-order", payload={"answer": {"x": owner}},
        )
    one = runtime.trajectory.list_events(tenant_id="school", owner_user_id="u1")
    two = runtime.trajectory.list_events(tenant_id="school", owner_user_id="u2")
    assert len(one) == len(two) == 1
    assert one[0]["owner_user_id"] == "u1"
    assert two[0]["owner_user_id"] == "u2"


def test_calibration_refuses_candidate_without_enough_real_attempts():
    runtime, _, _, _ = build_runtime()
    for index in range(3):
        runtime.trajectory.record(
            event_type="task_completed", source="test", tenant_id="school", owner_user_id="u1",
            session_id="s1", task_id=f"T-{index}", outcome="success", updated_by="u1",
        )
    result = runtime.calibration.build_candidate(tenant_id="school", min_samples=10, updated_by="admin")
    assert result["status"] == "insufficient_data"
    assert result["candidate"] is None


@pytest.mark.asyncio
async def test_calibrated_policy_changes_support_timing_but_keeps_bounded_tools():
    runtime, _, _, _ = build_runtime()
    # Seven easy successes plus three supported successes create enough real task groups
    # to move the hint later without changing any safety/authority boundary.
    for index in range(10):
        task_id = f"REAL-{index}"
        if index >= 7:
            runtime.trajectory.record(
                event_type="hint_requested", source="foundation", tenant_id="school", owner_user_id="u1",
                session_id="s1", task_id=task_id, outcome="neutral", updated_by="u1",
            )
        runtime.trajectory.record(
            event_type="task_completed", source="foundation", tenant_id="school", owner_user_id="u1",
            session_id="s1", task_id=task_id, outcome="success", updated_by="u1",
        )
    candidate_result = runtime.calibration.build_candidate(tenant_id="school", min_samples=10, updated_by="admin")
    candidate = candidate_result["candidate"]
    assert candidate and candidate["hint_at_failure"] == 3
    active = runtime.calibration.activate(candidate["profile_id"], tenant_id="school", updated_by="admin")
    assert active.status == "active"
    actions = []
    for _ in range(3):
        result = await runtime.step(
            AgentStepRequest(event_type="task_failed", task_result={"ok": False, "issues": ["还没有按同一标准完成"]}, use_model=False),
            tenant_id="school", owner_user_id="u1", session_id="s1", updated_by="u1",
        )
        actions.append(result["decision"]["action"])
    assert actions == ["ASK", "EXPLAIN", "HINT"]
    assert {item["name"] for item in runtime.tools.manifest()} == {
        "read_foundation", "next_hint", "request_evidence", "create_revision_task",
        "verification_snapshot", "assign_transfer", "advance", "escalate_human",
    }


def test_human_trajectory_labels_feed_calibration_evaluation():
    runtime, _, _, _ = build_runtime()
    event = runtime.ingest_server_event(
        event_type="task_failed", source="foundation", tenant_id="school", owner_user_id="u1", session_id="s1",
        actor_user_id="u1", task_id="FND-01-order", outcome="failure",
        payload={"task_result": {"ok": False, "issues": ["缺少判断依据"]}},
    )["event"]
    labeled = runtime.label_trajectory_event(
        event["event_id"], tenant_id="school", owner_user_id="u1", session_id="s1", actor_user_id="teacher-1",
        diagnosis_correct=True, observed_diagnosis="REASON_GAP", outcome="success", notes="教师确认该诊断可用",
    )
    metrics = labeled["calibration"]
    assert metrics["humanLabelCount"] == 1
    assert metrics["diagnosisAgreementRate"] == 1.0
