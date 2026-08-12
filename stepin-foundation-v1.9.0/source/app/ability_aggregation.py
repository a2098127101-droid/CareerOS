from __future__ import annotations

import json
from typing import Any

ABILITY_KEYWORDS = {
    "understand_task": ["任务", "要求", "目标"],
    "extract_info": ["检查", "识别", "信息", "证据", "访谈", "数据"],
    "organize_info": ["归类", "分类", "编码", "整理", "矩阵"],
    "judge": ["判断", "决策", "优先级", "比较", "选择", "初筛"],
    "spot_problem": ["异常", "问题", "检查", "风险"],
    "explain_reason": ["理由", "证据表达", "建议", "判断"],
    "deliver_clear": ["摘要", "报告", "建议", "交付", "方案"],
    "revise_feedback": ["修改", "迭代", "修订"],
    "transfer": ["迁移", "陌生", "独立"],
    "articulate": ["表达", "复盘", "求职", "汇报"],
}


def _meta(row: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(row.get("metadata_json") or "{}")
    except Exception:
        return {}


def aggregate_professional_evidence(evidence_items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Map later task evidence back to the public ability layer without pretending equivalence.

    This is a signal layer, not a verification engine. It counts repeated appearances of a public
    ability across different task evidence rows and keeps source IDs for auditability.
    """
    out = {aid: {"count": 0, "verifiedCount": 0, "sources": []} for aid in ABILITY_KEYWORDS}
    for row in evidence_items:
        label = str(row.get("source_label") or "")
        if label.startswith("基础实践"):
            continue
        meta = _meta(row)
        capabilities = " ".join(str(x) for x in (meta.get("capabilities") or []))
        hay = " ".join([label, str(row.get("content") or ""), capabilities])
        for aid, words in ABILITY_KEYWORDS.items():
            if any(w in hay for w in words):
                slot = out[aid]
                slot["count"] += 1
                if bool(row.get("verified")):
                    slot["verifiedCount"] += 1
                slot["sources"].append({
                    "evidenceId": row.get("evidence_id") or "",
                    "label": label,
                    "verified": bool(row.get("verified")),
                })
    return out
