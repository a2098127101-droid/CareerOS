from __future__ import annotations

from typing import Any

from .models import AgentAction, DiagnosisCode


class LearnerAgentTools:
    """Narrow tool contract between the agent and CareerOS domain services.

    The runtime never reaches into database tables or app.main globals. All mutations
    pass through this adapter so the same agent can later be hosted in another process.
    """

    CONTRACT = {
        "read_foundation": {"mutating": False, "description": "读取当前实践、能力与解锁状态"},
        "next_hint": {"mutating": True, "description": "消费一次现有脚手架提示预算"},
        "request_evidence": {"mutating": True, "description": "创建过程证据补充任务"},
        "create_revision_task": {"mutating": True, "description": "把教师反馈转成学生修订任务"},
        "verification_snapshot": {"mutating": False, "description": "读取完成、迁移与能力证据状态"},
        "assign_transfer": {"mutating": False, "description": "读取下一项跨材料迁移任务"},
        "advance": {"mutating": False, "description": "读取系统决定的下一阶段，不自行绕过 Gate"},
        "escalate_human": {"mutating": True, "description": "创建人工评审任务"},
    }

    def __init__(self, *, foundation: Any, collaboration: Any):
        self.foundation = foundation
        self.collaboration = collaboration

    @classmethod
    def manifest(cls) -> list[dict[str, Any]]:
        return [{"name": name, **meta} for name, meta in cls.CONTRACT.items()]

    def summary(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        return self.foundation.summary(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
        )

    def task_context(self, task_id: str, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        if not task_id:
            return {}
        try:
            return self.foundation.get_task(
                task_id,
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                session_id=session_id,
            )
        except (KeyError, Exception) as exc:
            if exc.__class__.__name__ not in {"KeyError", "FoundationError"}:
                raise
            return {}

    def open_feedback(self, *, tenant_id: str, session_id: str) -> list[dict[str, Any]]:
        rows = self.collaboration.list_feedback(session_id, tenant_id=tenant_id)
        return [row for row in rows if str(row.get("status") or "open") not in {"resolved", "done", "completed"}]

    def open_revision_tasks(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> list[dict[str, Any]]:
        rows = self.collaboration.list_tasks(
            tenant_id=tenant_id,
            session_id=session_id,
            owner_user_id=owner_user_id,
            limit=200,
        )
        types = {"learner_revision", "practice_revision", "revision"}
        return [
            row for row in rows
            if str(row.get("task_type") or "") in types
            and str(row.get("status") or "todo") in {"todo", "doing"}
        ]

    def execute(
        self,
        action: AgentAction,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        task_id: str,
        diagnosis: DiagnosisCode,
        updated_by: str,
        summary: dict[str, Any],
        task_context: dict[str, Any],
        open_feedback: list[dict[str, Any]],
    ) -> tuple[str, dict[str, Any]]:
        if action == AgentAction.HINT:
            if not task_id:
                return "next_hint", {"available": False, "message": "当前没有可提示的任务"}
            result = self.foundation.hint(
                task_id,
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
                session_id=session_id,
                updated_by=updated_by,
            )
            return "next_hint", dict(result or {})

        if action == AgentAction.REQUEST_EVIDENCE:
            task = self.collaboration.ensure_task(
                title="补充你这一步是怎么判断的",
                task_type="learner_evidence_request",
                session_id=session_id,
                tenant_id=tenant_id,
                priority="normal",
                source="stepin_learner_agent",
                owner_user_id=owner_user_id,
                payload={"taskId": task_id, "diagnosis": diagnosis.value},
            )
            return "request_evidence", {"task": task}

        if action == AgentAction.CREATE_REVISION_TASK:
            feedback = open_feedback[0] if open_feedback else {}
            task = self.collaboration.ensure_task(
                title="根据老师的意见再改一版",
                task_type="learner_revision",
                session_id=session_id,
                tenant_id=tenant_id,
                priority="high" if str(feedback.get("priority") or "") == "high" else "normal",
                source="stepin_learner_agent",
                owner_user_id=owner_user_id,
                payload={
                    "taskId": task_id,
                    "diagnosis": diagnosis.value,
                    "feedbackId": feedback.get("feedback_id") or "",
                    "feedback": str(feedback.get("content") or "")[:2000],
                },
            )
            return "create_revision_task", {"task": task}

        if action == AgentAction.VERIFY:
            abilities = summary.get("abilities") or []
            return "verification_snapshot", {
                "foundationComplete": bool(summary.get("foundationComplete")),
                "professionalUnlocked": bool(summary.get("professionalUnlocked")),
                "mode": summary.get("mode"),
                "abilities": [
                    {
                        "id": row.get("id"),
                        "level": row.get("level"),
                        "independent": row.get("independent", 0),
                        "transfer": row.get("transfer", 0),
                        "laterVerifiedCount": row.get("laterVerifiedCount", 0),
                    }
                    for row in abilities
                ],
            }

        if action == AgentAction.ASSIGN_TRANSFER:
            return "assign_transfer", {
                "next": ((summary.get("exploration") or {}).get("next") or {}),
                "completed": (summary.get("exploration") or {}).get("completed", 0),
                "total": (summary.get("exploration") or {}).get("total", 0),
            }

        if action == AgentAction.ADVANCE:
            current = summary.get("currentTask") or ((summary.get("exploration") or {}).get("next") or {})
            return "advance", {
                "mode": summary.get("mode"),
                "professionalUnlocked": bool(summary.get("professionalUnlocked")),
                "next": current,
                "href": "/projects" if summary.get("professionalUnlocked") else "/static/foundation.html",
            }

        if action == AgentAction.ESCALATE:
            task = self.collaboration.ensure_task(
                title="Learner Agent 请求人工介入",
                task_type="learner_human_review",
                session_id=session_id,
                tenant_id=tenant_id,
                priority="high",
                source="stepin_learner_agent",
                owner_user_id=owner_user_id,
                payload={
                    "taskId": task_id,
                    "diagnosis": diagnosis.value,
                    "reason": "连续干预后仍未解决，Agent 不继续提高答案暴露程度。",
                },
            )
            return "escalate_human", {"task": task}

        return "", {}
