from __future__ import annotations

import re
from .models import EvidenceAudit

NUMBER_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:\d+(?:\.\d+)?%|\d+(?:\.\d+)?(?:万|千|百)?(?:元|人|次|项|个|名|家|所|年|月|天|小时|分钟|分))"
)


def _normalize_number(token: str) -> str:
    return token.replace(",", "").strip()


def audit_evidence(text: str, evidence: str) -> EvidenceAudit:
    """Conservative numerical evidence lock.

    Numbers in generated text that never appear in the user's evidence are
    flagged. This is not a full hallucination detector; prompts also prohibit
    invented facts, awards, roles and metrics.
    """
    text_numbers = {_normalize_number(x) for x in NUMBER_PATTERN.findall(text)}
    evidence_numbers = {_normalize_number(x) for x in NUMBER_PATTERN.findall(evidence)}
    unsupported = sorted(x for x in text_numbers if x and x not in evidence_numbers)

    warnings: list[str] = []
    if unsupported:
        warnings.append("生成文本出现未在用户事实材料中找到的数字，请逐项核实或删除。")
    if "[待确认]" in text or "【待确认】" in text:
        warnings.append("文本仍包含待确认占位符，提交前必须人工核验。")

    return EvidenceAudit(
        passed=not unsupported,
        unsupported_numbers=unsupported,
        warnings=warnings,
    )
