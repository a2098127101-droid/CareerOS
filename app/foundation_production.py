from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .foundation_progress import FoundationError, FoundationProgressService


EXPLORATIONS: dict[str, dict[str, Any]] = {
    "information": {
        "id": "information",
        "title": "从材料里找重点",
        "intro": "换一份材料，只留下真正影响下一步的关键信息。",
        "type": "select",
        "abilities": ["extract_info", "organize_info"],
        "data": {
            "question": "周四 16:00 前要交报名汇总。下面 5 条里，哪 3 条最影响你把事情按时交出去？",
            "pick": 3,
            "items": [
                {"id": "deadline", "text": "最终汇总周四 16:00 前提交。"},
                {"id": "missing", "text": "还有 12 人没有回复是否参加。"},
                {"id": "format", "text": "最终要交姓名、电话、是否参加三列。"},
                {"id": "poster", "text": "上次活动海报是蓝色。"},
                {"id": "water", "text": "有人建议现场准备瓶装水。"},
            ],
        },
    },
    "judgment": {
        "id": "judgment",
        "title": "换件事再做一次判断",
        "intro": "这次不告诉你方法，自己判断哪件事应该先处理。",
        "type": "choice_reason",
        "abilities": ["judge", "explain_reason"],
        "data": {
            "question": "现在是上午 9:30，只能先处理一件事，你会先做哪件？",
            "items": [
                {"id": "link", "title": "修复报名链接", "detail": "40 人今天 12:00 前要报名，但链接打不开。"},
                {"id": "slides", "title": "美化下周汇报", "detail": "下周一才汇报，内容已经完整。"},
                {"id": "archive", "title": "整理旧文件", "detail": "没有明确截止时间。"},
            ],
        },
    },
    "expression": {
        "id": "expression",
        "title": "把事情交代清楚",
        "intro": "把一件已经做到一半的事情交给下一位，让对方不用重新猜。",
        "type": "text",
        "abilities": ["deliver_clear", "articulate"],
        "data": {
            "situation": "30 人报名已经确认 24 人，还有 6 人没回复；名单周四 16:00 前必须提交。你现在要把事情交给下一位同学。",
            "placeholder": "说清楚：已经做到哪、还差什么、下一步先做什么。",
        },
    },
}


class ExplorationRequest(BaseModel):
    answer: dict[str, Any] = Field(default_factory=dict)


class ProductionFoundationFacade:
    """Extend the shared Foundation runtime with post-foundation exploration.

    Repository selection and HTTP registration intentionally live in
    ``foundation_registration.py`` so this domain layer stays database-agnostic.
    """

    def __init__(self, service: FoundationProgressService):
        self.service = service

    def __getattr__(self, name: str):
        return getattr(self.service, name)

    @staticmethod
    def _exploration_rows(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        rows = state.get("explorations") or {}
        return rows if isinstance(rows, dict) else {}

    def summary(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        base = dict(self.service.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id))
        state = self.service.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        rows = self._exploration_rows(state)
        completed_types = [kind for kind in EXPLORATIONS if kind in rows]
        expression_done = bool(base.get("expression"))
        foundation_done = bool(base.get("foundationComplete"))
        unlocked = foundation_done and expression_done and len(completed_types) >= len(EXPLORATIONS)
        next_kind = next((kind for kind in EXPLORATIONS if kind not in rows), "")
        base["professionalUnlocked"] = unlocked
        base["mode"] = (
            "professional_ready"
            if unlocked
            else "exploration"
            if foundation_done and expression_done
            else "expression"
            if foundation_done
            else "beginner"
        )
        base["exploration"] = {
            "completed": len(completed_types),
            "total": len(EXPLORATIONS),
            "completedTypes": completed_types,
            "next": EXPLORATIONS.get(next_kind) if next_kind else None,
        }
        return base

    def teacher_growth(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        data = dict(self.service.teacher_growth(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id))
        data["summary"] = self.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        return data

    @staticmethod
    def _validate_exploration(kind: str, answer: dict[str, Any]) -> tuple[bool, str]:
        if kind == "information":
            selected = set(answer.get("selected") or [])
            if selected != {"deadline", "missing", "format"}:
                return False, "再看一次：时间、还缺什么、最后要交成什么样，最影响下一步。"
            return True, ""
        if kind == "judgment":
            if str(answer.get("choice") or "") != "link":
                return False, "先比较哪件事如果现在不处理，会马上影响更多人。"
            if len(str(answer.get("reason") or "").strip()) < 12:
                return False, "再说一句为什么先处理它。"
            return True, ""
        if kind == "expression":
            text = str(answer.get("text") or "").strip()
            if len(text) < 45:
                return False, "再具体一点，把已经做到哪、还差什么、下一步做什么都说清楚。"
            if not any(token in text for token in ("24", "6", "周四", "16")):
                return False, "把关键数字或截止时间写进去，下一位才不用重新猜。"
            return True, ""
        return False, "未知探索任务"

    def exploration_task(self, kind: str, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        if kind not in EXPLORATIONS:
            raise KeyError(kind)
        summary = self.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        if not summary.get("foundationComplete") or not summary.get("expression"):
            raise FoundationError("先完成前面的基础练习和表达练习")
        rows = summary.get("exploration") or {}
        completed = set(rows.get("completedTypes") or [])
        if kind in completed:
            return {"ok": True, "done": True, "task": EXPLORATIONS[kind]}
        next_task = (rows.get("next") or {}).get("id")
        if next_task and next_task != kind:
            raise FoundationError("先完成眼前这一种材料，再换下一种")
        return {"ok": True, "done": False, "task": EXPLORATIONS[kind]}

    def complete_exploration(
        self,
        kind: str,
        answer: dict[str, Any],
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        updated_by: str,
    ) -> dict[str, Any]:
        self.exploration_task(kind, tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        ok, issue = self._validate_exploration(kind, answer or {})
        if not ok:
            return {"ok": False, "issues": [issue], "task": EXPLORATIONS[kind]}

        state = self.service.get_state(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        rows = self._exploration_rows(state)
        if kind not in rows:
            task = EXPLORATIONS[kind]
            evidence = self.service.evidence.add_structured(
                session_id,
                title=f"跨材料探索 · {task['title']}",
                action=f"在新的{task['title']}材料中独立完成一次任务。",
                proof=str(answer)[:4000],
                capabilities=list(task.get("abilities") or []),
                verified=False,
                tenant_id=tenant_id,
                owner_user_id=owner_user_id,
            )
            rows[kind] = {
                "kind": kind,
                "title": task["title"],
                "answer": dict(answer or {}),
                "evidenceId": evidence.get("evidence_id") or evidence.get("id") or "",
                "completedAt": self.service._now(),
            }
            state["explorations"] = rows
            abilities = dict(state.get("abilities") or {})
            for aid in task.get("abilities") or []:
                row = dict(abilities.get(aid) or {"id": aid, "name": aid})
                row["attempts"] = int(row.get("attempts") or 0) + 1
                row["independent"] = int(row.get("independent") or 0) + 1
                row["transfer"] = int(row.get("transfer") or 0) + 1
                row["scoreTotal"] = round(float(row.get("scoreTotal") or 0.0) + 1.0, 3)
                abilities[aid] = row
            state["abilities"] = abilities
            self.service._save(state, tenant_id=tenant_id, owner_user_id=owner_user_id, updated_by=updated_by)

        return {
            "ok": True,
            "summary": self.summary(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id),
        }
