from __future__ import annotations

from typing import Any


def build_first_mini_project(task_results: dict[str, Any]) -> dict[str, Any]:
    """Turn the public-practice task chain into one small project summary."""
    result = task_results.get("FND-08-mini-project") or {}
    answer = result.get("answer") or {}
    key_facts = answer.get("keyFacts") or []
    decision = str(answer.get("decision") or "").strip()
    handoff = str(answer.get("handoff") or "").strip()
    return {
        "id": "FOUNDATION-PROJECT-01",
        "title": "第一次把一件小事完整做完",
        "plainTitle": "活动信息整理与处理说明",
        "taskIds": [
            "FND-02-key-info", "FND-03-group", "FND-04-find-problem",
            "FND-05-handoff", "FND-07-transfer", "FND-08-mini-project",
        ],
        "keyFacts": list(key_facts),
        "decision": decision,
        "handoff": handoff,
        "summary": "你先找重点，再判断先处理什么，最后把结果交代清楚。前面分开的几个小动作已经连成一个小项目。",
    }


def mini_project_markdown(project: dict[str, Any]) -> str:
    facts = "\n".join(f"- {x}" for x in (project.get("keyFacts") or [])) or "- 已完成关键信息整理"
    return (
        f"# {project.get('plainTitle') or project.get('title')}\n\n"
        "## 我先抓到的重点\n"
        f"{facts}\n\n"
        "## 我做的判断\n"
        f"{project.get('decision') or '已完成处理顺序判断'}\n\n"
        "## 我怎么交代结果\n"
        f"{project.get('handoff') or '已完成一页交接说明'}\n\n"
        "## 这次练到的做事方法\n"
        "先看清要求，再找重点；做判断时说明理由；最后让下一位知道接下来怎么继续。\n"
    )
