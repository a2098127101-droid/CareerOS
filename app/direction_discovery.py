from __future__ import annotations

from typing import Any


def discover_task_preferences(task_results: dict[str, Any]) -> dict[str, Any]:
    """Post-foundation task preference hints. Intentionally avoids job titles."""
    buckets = {
        "信息": {"tasks": {"FND-02-key-info", "FND-03-group", "FND-04-find-problem"}, "score": 0.0},
        "判断": {"tasks": {"FND-01-order", "FND-07-transfer", "FND-08-mini-project"}, "score": 0.0},
        "表达": {"tasks": {"FND-05-handoff", "FND-06-revise", "FND-08-mini-project"}, "score": 0.0},
    }
    for name, bucket in buckets.items():
        vals = []
        for tid in bucket["tasks"]:
            row = task_results.get(tid) or {}
            if row:
                score = float(row.get("score") or 0)
                hints = int(row.get("hintsUsed") or 0)
                vals.append(max(0.0, score - min(0.25, hints * 0.08)))
        bucket["score"] = round(sum(vals) / len(vals), 3) if vals else 0.0
        bucket.pop("tasks", None)
    ordered = sorted(buckets.items(), key=lambda kv: (-kv[1]["score"], kv[0]))
    top = ordered[0][0] if ordered else ""
    label = {
        "信息": "你目前在‘找重点、理信息’这类任务上更顺手。",
        "判断": "你目前在‘比较、取舍、说明理由’这类任务上更顺手。",
        "表达": "你目前在‘把事情讲清楚、按反馈修改’这类任务上更顺手。",
    }.get(top, "先继续多做几类任务，再看自己更顺手哪一种。")
    return {"unlocked": bool(task_results.get("FND-08-mini-project")), "buckets": buckets, "top": top, "message": label}
