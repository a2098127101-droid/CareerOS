from __future__ import annotations

from typing import Any


class ExpressionService:
    """Turns completed practice into three plain-language expression outputs."""

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        text = " ".join(str(text or "").replace("\n", " ").split()).strip("，。；; ")
        return text[:limit]

    @classmethod
    def build(cls, project: dict[str, Any], *, reflection: str = "") -> dict[str, Any]:
        title = project.get("plainTitle") or project.get("title") or "一次实践"
        decision = cls._clip(project.get("decision") or "整理材料并确定了处理顺序", 42)
        handoff = cls._clip(project.get("handoff") or "把结果整理成了可交接的说明", 42)
        reflection = cls._clip(reflection, 90)
        resume = f"完成{title}：从材料中提取关键信息，确定处理顺序并说明理由，最后整理成可交接的处理说明。"
        interview = (
            f"我做过一次{title}。开始时材料比较杂，我先找出真正影响任务的重点，再比较哪些问题应该先处理。"
            f"我的主要判断是：{decision}。之后我把结果整理给下一位同学，重点说清已经发现什么、准备先做什么和下一步怎么继续。"
            + (f"复盘时我发现：{reflection}。" if reflection else "")
        )
        reflection_text = reflection or "这次我发现，先把要求和关键信息理清楚，再做判断，会比一上来就动手更稳。"
        return {
            "selfReview": reflection_text,
            "resume": resume,
            "interview90s": interview,
            "plain": "同一段实践，分别练成‘自己能复盘、简历能写、面试能讲’三种表达。",
        }
