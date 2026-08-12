from __future__ import annotations

from collections import Counter
from typing import Any

from ..foundation_abilities import TASK_BY_ID
from .models import AgentAction, LearnerAgentState


class LearnerAgentEvaluator:
    """Runtime evaluation for policy compliance and pedagogical failure modes."""

    LEAK_PHRASES = (
        "正确答案是",
        "答案是",
        "答案为",
        "直接选择",
        "你应该选择",
        "你应该填",
        "照着写",
        "最终答案",
    )

    @staticmethod
    def _expected_tokens(task_id: str) -> list[str]:
        task = TASK_BY_ID.get(task_id) or {}
        data = task.get("data") or {}
        item_text: dict[str, str] = {}
        for item in data.get("items") or []:
            if isinstance(item, dict) and item.get("id"):
                item_text[str(item["id"])] = str(item.get("title") or item.get("text") or "")
        for item in data.get("issues") or []:
            if isinstance(item, dict) and item.get("id"):
                item_text[str(item["id"])] = str(item.get("text") or "")
        for item in data.get("facts") or []:
            if isinstance(item, dict) and item.get("id"):
                item_text[str(item["id"])] = str(item.get("text") or "")
        expected: list[str] = []
        raw = data.get("expected")
        if isinstance(raw, str):
            expected.append(item_text.get(raw, raw))
        elif isinstance(raw, list):
            expected.extend(item_text.get(str(x), str(x)) for x in raw)
        raw_top = data.get("expectedTop") or []
        expected.extend(item_text.get(str(x), str(x)) for x in raw_top)
        raw_key = data.get("expectedKey") or []
        expected.extend(item_text.get(str(x), str(x)) for x in raw_key)
        return [x.strip() for x in expected if len(x.strip()) >= 4]

    def evaluate_output(self, *, action: AgentAction, output_text: str, task_id: str = "") -> dict[str, Any]:
        text = str(output_text or "")
        expected_tokens = self._expected_tokens(task_id)
        phrase_leak = any(token in text for token in self.LEAK_PHRASES)
        expected_leaks = [token for token in expected_tokens if token and token in text]
        guarded_action = action in {AgentAction.ASK, AgentAction.HINT, AgentAction.EXPLAIN, AgentAction.SHOW_RESOURCE}
        direct_answer_leak = bool(guarded_action and (phrase_leak or expected_leaks))
        return {
            "boundedAction": action.value in {x.value for x in AgentAction},
            "directAnswerLeak": direct_answer_leak,
            "leakSignals": (["answer_phrase"] if phrase_leak else []) + [f"expected:{x[:80]}" for x in expected_leaks[:3]],
            "safe": not direct_answer_leak,
        }

    def summarize(self, events: list[dict[str, Any]], state: LearnerAgentState) -> dict[str, Any]:
        decisions = [row for row in events if str(row.get("kind") or "") == "decision"]
        total = len(decisions)
        actions = Counter(str(row.get("action") or "") for row in decisions)
        diagnoses = Counter(str(row.get("diagnosis") or "") for row in decisions)
        leaks = sum(1 for row in decisions if (row.get("evaluation") or {}).get("directAnswerLeak"))
        model_used = sum(1 for row in decisions if bool((row.get("model") or {}).get("used")))
        over_help = sum(
            1 for row in decisions
            if str(row.get("action") or "") in {AgentAction.HINT.value, AgentAction.EXPLAIN.value}
            and str(row.get("diagnosis") or "") == "PROGRESS"
            and int(row.get("failureStreak") or 0) == 0
        )
        advance_without_unlock = sum(
            1 for row in decisions
            if str(row.get("action") or "") == AgentAction.ADVANCE.value
            and not bool(row.get("professionalUnlocked"))
            and str(row.get("diagnosis") or "") != "SUCCESS"
        )
        ladder_violations = 0
        for row in decisions:
            streak = int(row.get("failureStreak") or 0)
            action = str(row.get("action") or "")
            if streak == 1 and action not in {AgentAction.ASK.value, AgentAction.HINT.value}:
                ladder_violations += 1
            elif streak == 4 and action not in {AgentAction.REQUEST_EVIDENCE.value, AgentAction.ESCALATE.value}:
                ladder_violations += 1
            elif streak >= 5 and action != AgentAction.ESCALATE.value:
                ladder_violations += 1
        verified_capabilities = sum(1 for row in state.capability_states.values() if row.stage == "verified")
        return {
            "decisions": total,
            "actionDistribution": dict(actions),
            "diagnosisDistribution": dict(diagnoses),
            "directAnswerLeakageRate": round(leaks / total, 4) if total else 0.0,
            "overHelpRate": round(over_help / total, 4) if total else 0.0,
            "advanceWithoutUnlock": advance_without_unlock,
            "policyLadderViolations": ladder_violations,
            "humanEscalationRate": round(actions.get(AgentAction.ESCALATE.value, 0) / total, 4) if total else 0.0,
            "modelUseRate": round(model_used / total, 4) if total else 0.0,
            "verifiedCapabilities": verified_capabilities,
            "agentHealthy": leaks == 0 and advance_without_unlock == 0 and ladder_violations == 0,
        }
