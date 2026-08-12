from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import AgentAction, DiagnosisCode, LearnerAgentState


@dataclass(frozen=True)
class PolicyDecision:
    action: AgentAction
    diagnosis: DiagnosisCode
    reason: str


class LearnerAgentPolicy:
    """Bounded, trajectory-calibratable practice policy.

    Only intervention timing is calibratable. Safety and authority boundaries remain
    fixed in code: the model cannot choose actions, bypass gates, create final answers,
    or mark a capability mastered.
    """

    ACTIONS = tuple(action.value for action in AgentAction)
    DEFAULT_PROFILE = {
        "ask_until_failure": 1,
        "hint_at_failure": 2,
        "explain_until_failure": 3,
        "request_evidence_at_failure": 4,
        "escalate_at_failure": 5,
    }

    @staticmethod
    def diagnose(
        state: LearnerAgentState,
        observation: dict[str, Any],
        *,
        summary: dict[str, Any],
        open_feedback: list[dict[str, Any]],
    ) -> DiagnosisCode:
        event_type = str(observation.get("event_type") or "user_message")
        result = observation.get("task_result") or {}
        issues = " ".join(str(x) for x in (result.get("issues") or []))
        message = str(observation.get("message") or "")

        if open_feedback or event_type in {"teacher_feedback", "revision_requested"}:
            return DiagnosisCode.REVISION_PENDING
        if event_type == "human_review_required":
            return DiagnosisCode.HUMAN_REVIEW
        if event_type in {"task_completed", "transfer_completed", "project_completed"} or result.get("ok") is True:
            return DiagnosisCode.SUCCESS
        if event_type in {"evidence_rejected", "evidence_partial"}:
            return DiagnosisCode.EVIDENCE_GAP
        if event_type in {"transfer_failed"}:
            return DiagnosisCode.TRANSFER_GAP
        if event_type in {"task_failed"} or result.get("ok") is False:
            if any(token in issues for token in ("为什么", "理由", "依据", "判断依据")):
                return DiagnosisCode.REASON_GAP
            if any(token in issues for token in ("重点", "关键信息", "缺", "证据", "找出来")):
                return DiagnosisCode.EVIDENCE_GAP
            if any(token in issues for token in ("交代", "具体", "数字", "截止", "下一步", "完整")):
                return DiagnosisCode.OUTPUT_GAP
            if any(token in issues for token in ("换", "场景", "材料", "迁移")):
                return DiagnosisCode.TRANSFER_GAP
            return DiagnosisCode.METHOD_GAP
        if event_type in {
            "answer_saved", "revision_submitted", "expression_submitted", "teacher_feedback_resolved",
            "evidence_verified", "project_started", "project_updated", "project_milestone", "human_review_resolved",
        }:
            return DiagnosisCode.PROGRESS
        if any(token in message for token in ("不知道怎么", "不会做", "没看懂", "什么意思", "从哪开始")):
            return DiagnosisCode.TASK_MODEL
        if summary.get("foundationComplete") and not summary.get("professionalUnlocked"):
            if str(summary.get("mode") or "") == "exploration":
                return DiagnosisCode.TRANSFER_GAP
            return DiagnosisCode.PROGRESS
        return DiagnosisCode.PROGRESS

    @staticmethod
    def next_failure_streak(state: LearnerAgentState, diagnosis: DiagnosisCode, observation: dict[str, Any]) -> int:
        if diagnosis == DiagnosisCode.SUCCESS:
            return 0
        event_type = str(observation.get("event_type") or "")
        failed = event_type in {"task_failed", "transfer_failed"} or (observation.get("task_result") or {}).get("ok") is False
        if not failed:
            return state.failure_streak
        if state.diagnosis == diagnosis:
            return state.failure_streak + 1
        return 1

    @staticmethod
    def _hint_available(task: dict[str, Any], hints_used: int) -> bool:
        return int(task.get("hintBudget") or 0) > int(hints_used or 0)

    @classmethod
    def thresholds(cls, profile: dict[str, Any] | None) -> dict[str, int]:
        raw = {**cls.DEFAULT_PROFILE, **(profile or {})}
        ask = max(1, min(2, int(raw.get("ask_until_failure") or 1)))
        hint = max(ask + 1, min(4, int(raw.get("hint_at_failure") or 2)))
        explain = max(hint, min(5, int(raw.get("explain_until_failure") or 3)))
        evidence = max(explain + 1, min(6, int(raw.get("request_evidence_at_failure") or 4)))
        escalate = max(evidence + 1, min(7, int(raw.get("escalate_at_failure") or 5)))
        return {
            "ask_until_failure": ask,
            "hint_at_failure": hint,
            "explain_until_failure": explain,
            "request_evidence_at_failure": evidence,
            "escalate_at_failure": escalate,
        }

    def choose(
        self,
        state: LearnerAgentState,
        observation: dict[str, Any],
        *,
        summary: dict[str, Any],
        task: dict[str, Any],
        hints_used: int,
        open_feedback: list[dict[str, Any]],
        open_revision_tasks: list[dict[str, Any]],
        policy_profile: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        diagnosis = self.diagnose(state, observation, summary=summary, open_feedback=open_feedback)
        streak = self.next_failure_streak(state, diagnosis, observation)
        message = str(observation.get("message") or "")
        event_type = str(observation.get("event_type") or "user_message")
        t = self.thresholds(policy_profile)

        if diagnosis == DiagnosisCode.HUMAN_REVIEW:
            return PolicyDecision(AgentAction.ESCALATE, diagnosis, "当前事件明确需要人工介入")
        if diagnosis == DiagnosisCode.REVISION_PENDING:
            if open_feedback and not open_revision_tasks:
                return PolicyDecision(AgentAction.CREATE_REVISION_TASK, diagnosis, "存在未处理的教师反馈，需要转成明确修订任务")
            return PolicyDecision(AgentAction.EXPLAIN, diagnosis, "先帮助学生理解反馈要求，再由学生自己修改")
        if diagnosis == DiagnosisCode.SUCCESS:
            if summary.get("professionalUnlocked"):
                return PolicyDecision(AgentAction.ADVANCE, diagnosis, "当前阶段已经满足服务器解锁条件")
            return PolicyDecision(AgentAction.VERIFY, diagnosis, "任务已完成，先验证本次表现并读取下一步")
        failed = event_type in {"task_failed", "transfer_failed"} or (observation.get("task_result") or {}).get("ok") is False
        if failed:
            if streak <= t["ask_until_failure"]:
                return PolicyDecision(AgentAction.ASK, diagnosis, "首次失败优先用诊断性追问定位问题，不直接给方法")
            if streak == t["hint_at_failure"] and self._hint_available(task, hints_used):
                return PolicyDecision(AgentAction.HINT, diagnosis, "重复失败后给最小提示，但仍不提供最终答案")
            if streak <= t["explain_until_failure"]:
                return PolicyDecision(AgentAction.EXPLAIN, diagnosis, "连续失败后解释缺失的方法，而不是代做")
            if streak == t["request_evidence_at_failure"]:
                return PolicyDecision(AgentAction.REQUEST_EVIDENCE, diagnosis, "要求展示中间判断过程，以区分理解问题和执行问题")
            if streak >= t["escalate_at_failure"]:
                return PolicyDecision(AgentAction.ESCALATE, diagnosis, "连续干预达到当前策略的人工介入阈值")
            return PolicyDecision(AgentAction.EXPLAIN, diagnosis, "尚未达到人工介入阈值，继续用方法解释而不增加答案暴露")
        if any(token in message for token in ("提示", "提醒一下")) and self._hint_available(task, hints_used):
            return PolicyDecision(AgentAction.HINT, diagnosis, "学生主动请求提示且仍有提示预算")
        if any(token in message for token in ("解释", "方法", "怎么判断", "怎么想")):
            return PolicyDecision(AgentAction.EXPLAIN, diagnosis, "学生主动请求方法说明")
        if str(summary.get("mode") or "") == "exploration":
            return PolicyDecision(AgentAction.ASSIGN_TRANSFER, DiagnosisCode.TRANSFER_GAP, "基础动作已完成，进入跨材料迁移验证")
        if not task and summary.get("professionalUnlocked"):
            return PolicyDecision(AgentAction.ADVANCE, diagnosis, "当前阶段已经完成")
        return PolicyDecision(AgentAction.ASK, diagnosis, "默认使用一个最小诊断问题推进当前实践")

    def guard(
        self,
        decision: PolicyDecision,
        *,
        state: LearnerAgentState,
        summary: dict[str, Any],
        task: dict[str, Any],
        hints_used: int,
        open_feedback: list[dict[str, Any]],
        policy_profile: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        action = decision.action
        t = self.thresholds(policy_profile)
        if action == AgentAction.HINT and not self._hint_available(task, hints_used):
            return PolicyDecision(AgentAction.EXPLAIN, decision.diagnosis, "提示预算已用完，改为解释方法")
        if action == AgentAction.ASSIGN_TRANSFER and str(summary.get("mode") or "") != "exploration":
            return PolicyDecision(AgentAction.ASK, decision.diagnosis, "尚未进入迁移阶段，不能提前分配迁移任务")
        if action == AgentAction.CREATE_REVISION_TASK and not open_feedback:
            return PolicyDecision(AgentAction.ASK, decision.diagnosis, "没有教师反馈，不能凭空创建修订任务")
        if action == AgentAction.ESCALATE and state.failure_streak < t["escalate_at_failure"] and decision.diagnosis != DiagnosisCode.HUMAN_REVIEW:
            return PolicyDecision(AgentAction.REQUEST_EVIDENCE, decision.diagnosis, "未达到人工升级阈值，先请求过程证据")
        return decision
