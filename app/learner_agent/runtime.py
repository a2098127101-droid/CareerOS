from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from ..unified_runtime_store import RuntimeVersionConflict
from .calibration import LearnerAgentCalibrationService
from .evaluation import LearnerAgentEvaluator
from .memory import LearnerAgentMemory
from .models import AgentAction, AgentDecision, AgentObservationRequest, AgentStepRequest, DiagnosisCode, LearnerAgentState
from .policy import LearnerAgentPolicy, PolicyDecision
from .state import LearnerAgentStateStore
from .tools import LearnerAgentTools
from .trajectory import LearnerTrajectoryStore


class LearnerAgentRuntime:
    AGENT_ID = "stepin-learner"
    VERSION = "2.2.0"

    def __init__(
        self,
        *,
        repository: Any,
        foundation: Any,
        collaboration: Any,
        career_agents: Any | None = None,
    ):
        self.state_store = LearnerAgentStateStore(repository)
        self.memory = LearnerAgentMemory(repository)
        self.policy = LearnerAgentPolicy()
        self.tools = LearnerAgentTools(foundation=foundation, collaboration=collaboration)
        self.evaluator = LearnerAgentEvaluator()
        self.trajectory = LearnerTrajectoryStore(repository)
        self.calibration = LearnerAgentCalibrationService(repository, self.trajectory)
        self.career_agents = career_agents

    @classmethod
    def manifest(cls) -> dict[str, Any]:
        return {
            "agentId": cls.AGENT_ID,
            "version": cls.VERSION,
            "protocol": "StepIn Learner Agent HTTP/1",
            "stateful": True,
            "components": ["State", "Policy", "Tools", "Memory", "Trajectory", "ExecutionLoop", "Evaluation", "Calibration"],
            "actions": [action.value for action in AgentAction],
            "guarantees": [
                "model_cannot_choose_tools",
                "model_cannot_mark_capability_mastered",
                "no_final_deliverable_generation",
                "server_authoritative_state",
                "human_escalation_after_repeated_failure",
                "real_task_events_become_agent_observations",
                "policy_calibration_requires_human_activation",
            ],
        }

    @staticmethod
    def _safe_observation(req: AgentObservationRequest) -> dict[str, Any]:
        def clip(value: Any, limit: int = 3000) -> Any:
            if isinstance(value, str):
                return value[:limit]
            if isinstance(value, dict):
                return {str(k)[:80]: clip(v, limit=1200) for k, v in list(value.items())[:40]}
            if isinstance(value, list):
                return [clip(v, limit=800) for v in value[:40]]
            return value

        return {
            "event_type": str(req.event_type or "user_message")[:80],
            "task_id": str(req.task_id or "")[:160],
            "message": str(req.message or "")[:3000],
            "answer": clip(req.answer or {}),
            "task_result": clip(req.task_result or {}),
            "client_context": clip(req.client_context or {}),
        }

    def _context(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        observation: dict[str, Any],
    ) -> dict[str, Any]:
        summary = self.tools.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        task_id = str(observation.get("task_id") or (summary.get("currentTask") or {}).get("id") or ((summary.get("exploration") or {}).get("next") or {}).get("id") or "")
        task_context = self.tools.task_context(
            task_id,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
        ) if task_id else {}
        task = dict(task_context.get("task") or {})
        hints_used = int(task_context.get("hintsUsed") or 0)
        open_feedback = self.tools.open_feedback(tenant_id=tenant_id, session_id=session_id)
        open_revision_tasks = self.tools.open_revision_tasks(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
        )
        return {
            "summary": summary,
            "taskId": task_id,
            "taskContext": task_context,
            "task": task,
            "hintsUsed": hints_used,
            "openFeedback": open_feedback,
            "openRevisionTasks": open_revision_tasks,
        }

    def _record_observation_trajectory(
        self,
        *,
        observation: dict[str, Any],
        context: dict[str, Any],
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        updated_by: str,
    ) -> dict[str, Any] | None:
        client_context = observation.get("client_context") or {}
        if client_context.get("_trajectory_recorded"):
            return None
        event_type = str(observation.get("event_type") or "user_message")
        result = observation.get("task_result") or {}
        if result.get("ok") is True:
            outcome = "success"
        elif result.get("ok") is False:
            outcome = "failure"
        else:
            outcome = "neutral"
        return self.trajectory.record(
            event_type=event_type,
            source=str(client_context.get("surface") or client_context.get("source") or "client"),
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            actor_user_id=updated_by,
            task_id=str(context.get("taskId") or observation.get("task_id") or ""),
            project_id=str(client_context.get("project_id") or client_context.get("projectId") or ""),
            evidence_id=str(client_context.get("evidence_id") or client_context.get("evidenceId") or ""),
            claim_id=str(client_context.get("claim_id") or client_context.get("claimId") or ""),
            outcome=outcome,
            correlation_id=str(client_context.get("correlation_id") or client_context.get("correlationId") or ""),
            payload={
                "message": observation.get("message") or "",
                "answer": observation.get("answer") or {},
                "task_result": result,
                "client_context": {k: v for k, v in client_context.items() if not str(k).startswith("_")},
            },
            updated_by=updated_by,
        )

    def _sync_trajectory_state(
        self,
        state: LearnerAgentState,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        metrics = self.calibration.analyze(
            tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, limit=1000
        )
        state.trajectory_event_count = int(metrics.get("eventCount") or 0)
        rows = self.trajectory.list_events(
            tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, limit=1
        )
        state.last_trajectory_event_id = str((rows[-1] if rows else {}).get("event_id") or "")
        distribution = metrics.get("challengeDistribution") or {}
        if distribution:
            state.challenge_state = max(distribution, key=lambda key: int(distribution.get(key) or 0))
        else:
            state.challenge_state = "unknown"
        profile = self.calibration.active_profile(tenant_id=tenant_id)
        state.policy_profile_version = profile.version
        return {"metrics": metrics, "profile": profile.model_dump(mode="json")}

    def ingest_server_event(
        self,
        *,
        event_type: str,
        source: str,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        actor_user_id: str = "",
        task_id: str = "",
        project_id: str = "",
        evidence_id: str = "",
        claim_id: str = "",
        outcome: str = "neutral",
        payload: dict[str, Any] | None = None,
        idempotency_key: str = "",
        correlation_id: str = "",
    ) -> dict[str, Any]:
        body = dict(payload or {})
        profile = self.calibration.active_profile(tenant_id=tenant_id)
        event = self.trajectory.record(
            event_type=event_type,
            source=source,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            actor_user_id=actor_user_id,
            task_id=task_id,
            project_id=project_id,
            evidence_id=evidence_id,
            claim_id=claim_id,
            outcome=outcome,
            correlation_id=correlation_id,
            policy_version=profile.version,
            payload=body,
            idempotency_key=idempotency_key,
            updated_by=actor_user_id or owner_user_id,
        )
        task_result = dict(body.get("task_result") or {})
        if "ok" not in task_result and outcome in {"success", "failure"}:
            task_result["ok"] = outcome == "success"
        if body.get("issues") and not task_result.get("issues"):
            task_result["issues"] = body.get("issues")
        req = AgentObservationRequest(
            event_type=event_type,
            task_id=task_id,
            message=str(body.get("message") or ""),
            answer=dict(body.get("answer") or {}),
            task_result=task_result,
            client_context={
                "source": source,
                "server_event": True,
                "_trajectory_recorded": True,
                "trajectoryEventId": event.get("event_id") or event.get("id"),
                "projectId": project_id,
                "evidenceId": evidence_id,
                "claimId": claim_id,
            },
        )
        observation = self.observe(
            req,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            updated_by=actor_user_id or owner_user_id,
        )
        return {"event": event, "observation": observation}

    def get_state(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> LearnerAgentState:
        state, version = self.state_store.load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        summary = self.tools.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        self.state_store.sync_from_foundation(state, summary)
        self._sync_trajectory_state(
            state, tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id
        )
        state, _ = self.state_store.save(
            state,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            updated_by=owner_user_id,
            expected_version=version,
        )
        return state

    def observe(
        self,
        req: AgentObservationRequest,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        updated_by: str,
    ) -> dict[str, Any]:
        observation = self._safe_observation(req)
        state, version = self.state_store.load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        context = self._context(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            observation=observation,
        )
        self.state_store.sync_from_foundation(state, context["summary"])
        self._record_observation_trajectory(
            observation=observation, context=context, tenant_id=tenant_id, owner_user_id=owner_user_id,
            session_id=session_id, updated_by=updated_by,
        )
        self._sync_trajectory_state(
            state, tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id
        )
        diagnosis = self.policy.diagnose(
            state,
            observation,
            summary=context["summary"],
            open_feedback=context["openFeedback"],
        )
        state.failure_streak = self.policy.next_failure_streak(state, diagnosis, observation)
        state.diagnosis = diagnosis
        state.pending_action = AgentAction.WAIT
        state.last_observation = observation
        state, _ = self.state_store.save(
            state,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            updated_by=updated_by,
            expected_version=version,
        )
        self.memory.record(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            kind="observation",
            updated_by=updated_by,
            payload={
                "eventType": observation["event_type"],
                "taskId": context["taskId"],
                "diagnosis": diagnosis.value,
                "failureStreak": state.failure_streak,
                "message": observation["message"][:600],
                "issues": (observation.get("task_result") or {}).get("issues") or [],
            },
        )
        return {"ok": True, "diagnosis": diagnosis.value, "state": state.model_dump(mode="json"), "context": self._public_context(context)}

    @staticmethod
    def _public_context(context: dict[str, Any]) -> dict[str, Any]:
        return {
            "taskId": context.get("taskId") or "",
            "task": context.get("task") or {},
            "hintsUsed": int(context.get("hintsUsed") or 0),
            "openFeedbackCount": len(context.get("openFeedback") or []),
            "openRevisionTaskCount": len(context.get("openRevisionTasks") or []),
            "mode": (context.get("summary") or {}).get("mode"),
            "professionalUnlocked": bool((context.get("summary") or {}).get("professionalUnlocked")),
        }

    def _fallback_response(
        self,
        decision: PolicyDecision,
        *,
        tool_result: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        diagnosis = decision.diagnosis
        if decision.action == AgentAction.ASK:
            prompts = {
                DiagnosisCode.TASK_MODEL: "先不做答案。用一句话告诉我：这一步最后要交出什么，最重要的限制是什么？",
                DiagnosisCode.REASON_GAP: "先不改你的结论。你刚才判断时主要用了哪两个标准？",
                DiagnosisCode.EVIDENCE_GAP: "先指出一条你认为最影响下一步的信息，再说它具体影响什么。",
                DiagnosisCode.OUTPUT_GAP: "假设下一位同学现在接手，他还缺哪一条信息才能继续做？",
                DiagnosisCode.METHOD_GAP: "先说说你现在是按什么标准比较这些材料的，不用先改答案。",
                DiagnosisCode.TRANSFER_GAP: "材料换了以后，你觉得前面哪一个做事方法还可以继续用？",
            }
            return prompts.get(diagnosis, "先用自己的话说一句：你准备先做什么，以及为什么这样做？")
        if decision.action == AgentAction.HINT:
            return str(tool_result.get("message") or "先只处理眼前最关键的一步，不需要一次完成全部。")
        if decision.action == AgentAction.EXPLAIN:
            explanations = {
                DiagnosisCode.TASK_MODEL: "先把任务拆成三件事：最后要交什么、什么时候要、哪些条件不能违反。先把这三项说清，再开始做。",
                DiagnosisCode.EVIDENCE_GAP: "判断一条信息是不是关键，可以问：删掉它以后，我还能不能按要求完成下一步？如果不能，它就更值得保留。",
                DiagnosisCode.REASON_GAP: "不要只给结论。先说你用的比较标准，再说明不这样处理会产生什么后果，理由就会更完整。",
                DiagnosisCode.OUTPUT_GAP: "交付是否清楚可以用三个问题检查：已经做到哪、还剩什么、下一步谁先做什么。",
                DiagnosisCode.TRANSFER_GAP: "迁移不是记住上一题答案，而是把上一题用过的判断标准带到新材料，再重新得出结论。",
                DiagnosisCode.REVISION_PENDING: "先把反馈改写成一个具体动作：要补什么、删什么或改清楚什么。只做这个改动，再比较新旧版本。",
            }
            return explanations.get(diagnosis, "先把当前方法说清楚，再按同一个标准重新做一次；我不会替你生成最终交付物。")
        if decision.action == AgentAction.REQUEST_EVIDENCE:
            return "把你刚才的中间判断过程写出来：你看到了什么、用了什么标准、为什么做这个选择。系统先看过程，不要求你换成漂亮答案。"
        if decision.action == AgentAction.CREATE_REVISION_TASK:
            return "老师的反馈已经转成一条明确的修订任务。先由你自己改出下一版，Agent 不会替你生成最终版本。"
        if decision.action == AgentAction.VERIFY:
            return "这次完成记录已经读取。系统不会因为一次做对就判定你已经掌握；还会看独立完成、换场景表现和后续证据。"
        if decision.action == AgentAction.ASSIGN_TRANSFER:
            title = str(((tool_result.get("next") or {}).get("title") or "下一份新材料"))
            return f"下一步换一份材料再做一次：{title}。这次尽量不用前面的提示，看看同一个方法能不能自己用出来。"
        if decision.action == AgentAction.ADVANCE:
            return "当前 Gate 已满足，可以进入下一阶段。这个动作只读取服务器的解锁结果，不会由 Agent 自己绕过条件。"
        if decision.action == AgentAction.ESCALATE:
            return "已经创建人工评审任务。连续提高提示强度会开始暴露答案，因此这里停止继续提示，交给老师或导师判断下一步。"
        if decision.action == AgentAction.SHOW_RESOURCE:
            return "先看当前任务的方法说明，只学习判断框架，不看这道任务的最终答案。"
        return "当前没有需要自动执行的动作。"

    async def _model_response(
        self,
        *,
        decision: PolicyDecision,
        observation: dict[str, Any],
        context: dict[str, Any],
        memory_snapshot: dict[str, Any],
        fallback: str,
        tenant_id: str,
        use_model: bool,
    ) -> tuple[str, dict[str, Any]]:
        if not use_model or decision.action not in {AgentAction.ASK, AgentAction.EXPLAIN, AgentAction.SHOW_RESOURCE}:
            return fallback, {"used": False, "reason": "bounded_deterministic_action"}
        if not self.career_agents or not self.career_agents.is_task_enabled("coach"):
            return fallback, {"used": False, "reason": "coach_route_unavailable"}
        system = (
            "你是 StepIn Learner Agent 的语言层，不是决策器。系统已经固定了动作。"
            "你只能完成指定动作，不能改变动作、不能给出正确选项、不能生成最终交付物、不能声称学生已经掌握能力。"
            "ASK 只问一个诊断问题；EXPLAIN 只解释方法，不套入本题最终答案；SHOW_RESOURCE 只给方法框架。"
            "输出简体中文，控制在120个汉字左右，不要提及内部Policy、State或工具名。"
        )
        user = json.dumps(
            {
                "fixedAction": decision.action.value,
                "diagnosis": decision.diagnosis.value,
                "task": context.get("task") or {},
                "learnerMessage": observation.get("message") or "",
                "learnerAnswer": observation.get("answer") or {},
                "issues": (observation.get("task_result") or {}).get("issues") or [],
                "repeatedPatterns": memory_snapshot.get("patterns") or {},
                "fallbackIntent": fallback,
            },
            ensure_ascii=False,
        )
        try:
            result = await self.career_agents.gateway.complete("coach", system, user, tenant_id=tenant_id)
            text = str(result.text or "").strip()
            evaluation = self.evaluator.evaluate_output(action=decision.action, output_text=text, task_id=context.get("taskId") or "")
            if not text or evaluation.get("directAnswerLeak"):
                return fallback, {
                    "used": True,
                    "accepted": False,
                    "providerId": result.provider_id,
                    "model": result.model,
                    "reason": "empty_or_answer_leak",
                }
            return text, {
                "used": True,
                "accepted": True,
                "providerId": result.provider_id,
                "model": result.model,
                "latencyMs": result.latency_ms,
                "totalTokens": result.total_tokens,
            }
        except Exception as exc:
            return fallback, {"used": False, "reason": "model_error", "error": str(exc)[:240]}

    async def step(
        self,
        req: AgentStepRequest,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        updated_by: str,
    ) -> dict[str, Any]:
        observation = self._safe_observation(req)
        state, version = self.state_store.load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        context = self._context(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            observation=observation,
        )
        self.state_store.sync_from_foundation(state, context["summary"])
        self._record_observation_trajectory(
            observation=observation, context=context, tenant_id=tenant_id, owner_user_id=owner_user_id,
            session_id=session_id, updated_by=updated_by,
        )
        trajectory_context = self._sync_trajectory_state(
            state, tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id
        )
        policy_profile = trajectory_context["profile"]
        raw_decision = self.policy.choose(
            state,
            observation,
            summary=context["summary"],
            task=context["task"],
            hints_used=context["hintsUsed"],
            open_feedback=context["openFeedback"],
            open_revision_tasks=context["openRevisionTasks"],
            policy_profile=policy_profile,
        )
        state.failure_streak = self.policy.next_failure_streak(state, raw_decision.diagnosis, observation)
        state.diagnosis = raw_decision.diagnosis
        guarded = self.policy.guard(
            raw_decision,
            state=state,
            summary=context["summary"],
            task=context["task"],
            hints_used=context["hintsUsed"],
            open_feedback=context["openFeedback"],
            policy_profile=policy_profile,
        )
        state.pending_action = guarded.action
        state.last_observation = observation
        state, version = self.state_store.save(
            state,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            updated_by=updated_by,
            expected_version=version,
        )

        tool_name, tool_result = self.tools.execute(
            guarded.action,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            task_id=context["taskId"],
            diagnosis=guarded.diagnosis,
            updated_by=updated_by,
            summary=context["summary"],
            task_context=context["taskContext"],
            open_feedback=context["openFeedback"],
        )
        fallback = self._fallback_response(guarded, tool_result=tool_result, context=context)
        memory_snapshot = self.memory.snapshot(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            limit=20,
        )
        response, model_meta = await self._model_response(
            decision=guarded,
            observation=observation,
            context=context,
            memory_snapshot=memory_snapshot,
            fallback=fallback,
            tenant_id=tenant_id,
            use_model=bool(req.use_model),
        )
        evaluation = self.evaluator.evaluate_output(
            action=guarded.action,
            output_text=response,
            task_id=context["taskId"],
        )
        if evaluation.get("directAnswerLeak"):
            response = fallback
            evaluation = self.evaluator.evaluate_output(
                action=guarded.action,
                output_text=response,
                task_id=context["taskId"],
            )
            model_meta = {**model_meta, "accepted": False, "reason": "runtime_leak_guard"}

        decision = AgentDecision(
            decision_id=f"LAD-{uuid4().hex[:12].upper()}",
            action=guarded.action,
            diagnosis=guarded.diagnosis,
            reason=guarded.reason,
            response=response,
            tool_name=tool_name,
            tool_result=tool_result,
            model=model_meta,
            evaluation=evaluation,
        )
        decision_payload = decision.model_dump(mode="json")
        intervention_event = self.trajectory.record(
            event_type="agent_intervention",
            source="learner_agent",
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            actor_user_id=updated_by,
            task_id=context["taskId"],
            outcome="neutral",
            intervention_id=decision.decision_id,
            policy_version=str(policy_profile.get("version") or ""),
            payload={
                "decisionId": decision.decision_id,
                "action": guarded.action.value,
                "diagnosis": guarded.diagnosis.value,
                "failureStreak": state.failure_streak,
                "model": model_meta,
                "toolName": tool_name,
            },
            updated_by=updated_by,
        )
        state.last_trajectory_event_id = str(intervention_event.get("event_id") or intervention_event.get("id") or "")
        state.trajectory_event_count += 1
        state.pending_action = AgentAction.WAIT
        state.last_decision = decision_payload
        state.last_evaluation = evaluation
        state.recent_interventions = (list(state.recent_interventions) + [
            {
                "decisionId": decision.decision_id,
                "taskId": context["taskId"],
                "diagnosis": guarded.diagnosis.value,
                "action": guarded.action.value,
                "failureStreak": state.failure_streak,
            }
        ])[-20:]
        try:
            state, version = self.state_store.save(
                state,
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                updated_by=updated_by,
                expected_version=version,
            )
        except RuntimeVersionConflict:
            latest, latest_version = self.state_store.load(
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                session_id=session_id,
            )
            self.state_store.sync_from_foundation(latest, context["summary"])
            latest.failure_streak = state.failure_streak
            latest.diagnosis = state.diagnosis
            latest.pending_action = AgentAction.WAIT
            latest.last_observation = observation
            latest.last_decision = decision_payload
            latest.last_evaluation = evaluation
            latest.recent_interventions = (list(latest.recent_interventions) + state.recent_interventions[-1:])[-20:]
            state, version = self.state_store.save(
                latest,
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                updated_by=updated_by,
                expected_version=latest_version,
            )

        self.memory.record(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            kind="observation",
            updated_by=updated_by,
            payload={
                "eventType": observation["event_type"],
                "taskId": context["taskId"],
                "diagnosis": guarded.diagnosis.value,
                "failureStreak": state.failure_streak,
                "message": observation["message"][:600],
                "issues": (observation.get("task_result") or {}).get("issues") or [],
            },
        )
        memory = self.memory.record(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            kind="decision",
            updated_by=updated_by,
            payload={
                "decisionId": decision.decision_id,
                "taskId": context["taskId"],
                "diagnosis": guarded.diagnosis.value,
                "action": guarded.action.value,
                "reason": guarded.reason,
                "failureStreak": state.failure_streak,
                "professionalUnlocked": bool(context["summary"].get("professionalUnlocked")),
                "model": model_meta,
                "evaluation": evaluation,
                "toolName": tool_name,
            },
        )
        trajectory_metrics = self.calibration.analyze(
            tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, limit=1000
        )
        aggregate_eval = self.evaluator.summarize(
            list(memory.get("events") or []), state, policy_profile=policy_profile, trajectory_metrics=trajectory_metrics
        )
        return {
            "ok": True,
            "agent": self.manifest(),
            "decision": decision_payload,
            "state": state.model_dump(mode="json"),
            "context": self._public_context(context),
            "evaluation": aggregate_eval,
        }

    def label_trajectory_event(
        self,
        event_id: str,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        actor_user_id: str,
        diagnosis_correct: bool | None = None,
        observed_diagnosis: str = "",
        outcome: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        rows = self.trajectory.list_events(
            tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, limit=LearnerTrajectoryStore.MAX_QUERY_EVENTS
        )
        target = next((row for row in rows if str(row.get("event_id") or row.get("id") or "") == event_id), None)
        if target is None:
            raise KeyError(event_id)
        profile = self.calibration.active_profile(tenant_id=tenant_id)
        label = self.trajectory.record(
            event_type="human_review_resolved",
            source="human_label",
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            actor_user_id=actor_user_id,
            task_id=str(target.get("task_id") or ""),
            project_id=str(target.get("project_id") or ""),
            evidence_id=str(target.get("evidence_id") or ""),
            claim_id=str(target.get("claim_id") or ""),
            outcome=(outcome if outcome in {"success", "failure", "neutral"} else "neutral"),
            correlation_id=event_id,
            policy_version=profile.version,
            payload={
                "targetEventId": event_id,
                "targetEventType": target.get("event_type") or "",
                "targetDiagnosis": ((target.get("payload") or {}).get("diagnosis") or ""),
                "diagnosisCorrect": diagnosis_correct,
                "observedDiagnosis": str(observed_diagnosis or "")[:80],
                "notes": str(notes or "")[:1200],
            },
            idempotency_key=f"human-label:{tenant_id}:{owner_user_id}:{event_id}:{actor_user_id}",
            updated_by=actor_user_id,
        )
        return {
            "ok": True,
            "label": label,
            "calibration": self.calibration.analyze(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id),
        }

    def evaluation_report(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        state = self.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        events = self.memory.recent(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            limit=LearnerAgentMemory.MAX_EVENTS,
        )
        profile = self.calibration.active_profile(tenant_id=tenant_id)
        trajectory_metrics = self.calibration.analyze(
            tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id, limit=2000
        )
        report = self.evaluator.summarize(
            events, state, policy_profile=profile.model_dump(mode="json"), trajectory_metrics=trajectory_metrics
        )
        report["trajectory"] = trajectory_metrics
        report["activePolicyProfile"] = profile.model_dump(mode="json")
        return report
