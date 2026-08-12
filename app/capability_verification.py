from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from .foundation_abilities import ABILITY_BY_ID, TASK_BY_ID


VERIFICATION_VERSION = "2.0-min"
LEVEL_UNOBSERVED = "unobserved"
LEVEL_SIGNAL = "signal"
LEVEL_EVIDENCE = "evidence"
LEVEL_VERIFIED = "verified_evidence"


class CapabilityVerificationService:
    """Derive conservative capability states from server-side practice evidence.

    This service is the authority boundary between practice telemetry and any visual
    representation. A client may render the returned level, but it must never infer or
    promote a capability from clicks, animation state, time-on-screen, or local scores.

    Minimal v2 policy:
    - Signal: the capability has been observed at least once.
    - Evidence: the same capability has succeeded across at least two task contexts and
      includes an independence/revision/transfer signal.
    - Verified Evidence: Evidence plus a transfer success and at least one canonical
      evidence item whose verification status is VERIFIED.
    """

    LEVELS = (LEVEL_UNOBSERVED, LEVEL_SIGNAL, LEVEL_EVIDENCE, LEVEL_VERIFIED)

    @staticmethod
    def _meta(row: dict[str, Any]) -> dict[str, Any]:
        raw = row.get("metadata")
        if isinstance(raw, dict):
            return raw
        try:
            return json.loads(row.get("metadata_json") or "{}")
        except Exception:
            return {}

    @staticmethod
    def _capability_ids_from_evidence(row: dict[str, Any]) -> set[str]:
        meta = CapabilityVerificationService._meta(row)
        raw = list(meta.get("capabilities") or [])
        by_name = {str(value.get("name") or ""): key for key, value in ABILITY_BY_ID.items()}
        ids: set[str] = set()
        for value in raw:
            token = str(value or "").strip()
            if token in ABILITY_BY_ID:
                ids.add(token)
            elif token in by_name:
                ids.add(by_name[token])
        return ids

    @staticmethod
    def _capability_ids_from_event(row: dict[str, Any]) -> set[str]:
        task_id = str(row.get("task_id") or "")
        ids = set(str(x) for x in ((TASK_BY_ID.get(task_id) or {}).get("abilities") or []))
        payload = row.get("payload") or {}
        if isinstance(payload, dict):
            raw = payload.get("capabilityIds") or payload.get("capability_ids") or []
            ids.update(str(x) for x in raw if str(x) in ABILITY_BY_ID)
        return {x for x in ids if x in ABILITY_BY_ID}

    def verify(
        self,
        *,
        foundation_summary: dict[str, Any],
        trajectory_events: list[dict[str, Any]],
        evidence_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        foundation_rows = {
            str(row.get("id") or ""): dict(row)
            for row in (foundation_summary.get("abilities") or [])
            if row.get("id") in ABILITY_BY_ID
        }
        success_tasks: dict[str, set[str]] = defaultdict(set)
        independent_tasks: dict[str, set[str]] = defaultdict(set)
        transfer_tasks: dict[str, set[str]] = defaultdict(set)
        revision_tasks: dict[str, set[str]] = defaultdict(set)
        event_sources: dict[str, list[dict[str, Any]]] = defaultdict(list)

        # V1 is intentionally excluded: a first draft is an observation/signal, not a
        # second successful context. V2 and transfer may contribute after server checks.
        successful_event_types = {
            "task_completed",
            "revision_submitted",
            "transfer_completed",
            "project_completed",
            "work_sample_v2_submitted",
            "work_sample_transfer_completed",
        }
        for event in trajectory_events:
            event_type = str(event.get("event_type") or "")
            outcome = str(event.get("outcome") or "neutral")
            if event_type not in successful_event_types or outcome == "failure":
                continue
            capability_ids = self._capability_ids_from_event(event)
            if not capability_ids:
                continue
            task_id = str(event.get("task_id") or event.get("project_id") or event.get("event_id") or "unknown")
            payload = event.get("payload") or {}
            independent = bool(isinstance(payload, dict) and payload.get("independent"))
            for capability_id in capability_ids:
                success_tasks[capability_id].add(task_id)
                if independent:
                    independent_tasks[capability_id].add(task_id)
                if event_type in {"transfer_completed", "work_sample_transfer_completed"}:
                    transfer_tasks[capability_id].add(task_id)
                if event_type in {"revision_submitted", "work_sample_v2_submitted"}:
                    revision_tasks[capability_id].add(task_id)
                event_sources[capability_id].append(
                    {
                        "type": "trajectory",
                        "id": str(event.get("event_id") or ""),
                        "taskId": task_id,
                        "eventType": event_type,
                        "at": str(event.get("occurred_at") or ""),
                    }
                )

        verified_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
        all_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in evidence_items:
            capability_ids = self._capability_ids_from_evidence(item)
            if not capability_ids:
                continue
            status = str(item.get("verification_status") or ("VERIFIED" if item.get("verified") else "SELF_REPORTED"))
            source = {
                "type": "evidence",
                "id": str(item.get("evidence_id") or ""),
                "label": str(item.get("source_label") or ""),
                "verificationStatus": status,
                "verified": status == "VERIFIED",
            }
            for capability_id in capability_ids:
                all_evidence[capability_id].append(source)
                if status == "VERIFIED":
                    verified_evidence[capability_id].append(source)

        records: list[dict[str, Any]] = []
        counts = {LEVEL_UNOBSERVED: 0, LEVEL_SIGNAL: 0, LEVEL_EVIDENCE: 0, LEVEL_VERIFIED: 0}
        for capability_id, definition in ABILITY_BY_ID.items():
            foundation = foundation_rows.get(capability_id) or {}
            attempts = int(foundation.get("attempts") or 0)
            guided = int(foundation.get("guided") or 0)
            independent = int(foundation.get("independent") or 0)
            transfer = int(foundation.get("transfer") or 0)
            combined = int(foundation.get("combined") or 0)
            later_practice = int(foundation.get("laterPracticeCount") or 0)

            # Foundation attempts correspond to completed immutable Foundation tasks.
            # Later evidence rows may be multiple versions of one task, so they are only
            # allowed to establish observation here; they cannot inflate task contexts.
            distinct_task_count = max(
                len(success_tasks[capability_id]),
                attempts,
                1 if later_practice > 0 else 0,
            )
            independent_count = max(len(independent_tasks[capability_id]), independent)
            transfer_count = max(len(transfer_tasks[capability_id]), transfer)
            revision_count = len(revision_tasks[capability_id])
            verified_count = len(verified_evidence[capability_id])
            observed = distinct_task_count > 0 or guided > 0 or bool(all_evidence[capability_id])
            independence_signal = independent_count > 0 or transfer_count > 0 or combined > 0 or revision_count > 0
            evidence_ready = distinct_task_count >= 2 and independence_signal
            verified_ready = evidence_ready and transfer_count >= 1 and verified_count >= 1

            if verified_ready:
                level = LEVEL_VERIFIED
            elif evidence_ready:
                level = LEVEL_EVIDENCE
            elif observed:
                level = LEVEL_SIGNAL
            else:
                level = LEVEL_UNOBSERVED
            counts[level] += 1

            confidence = 0.0
            if observed:
                confidence += 0.22
            confidence += min(distinct_task_count, 3) / 3 * 0.24
            if independence_signal:
                confidence += 0.18
            if transfer_count:
                confidence += 0.18
            if verified_count:
                confidence += 0.18
            confidence = round(min(confidence, 0.98), 3)

            requirements = {
                "observed": observed,
                "multipleTaskContexts": distinct_task_count >= 2,
                "independenceOrRevision": independence_signal,
                "transferSuccess": transfer_count >= 1,
                "canonicalVerifiedEvidence": verified_count >= 1,
            }
            next_required: list[str] = []
            if not observed:
                next_required.append("完成一次与该能力有关的真实任务")
            if observed and distinct_task_count < 2:
                next_required.append("在另一份不同任务或材料中再次做出来")
            if distinct_task_count >= 2 and not independence_signal:
                next_required.append("减少提示，独立完成或根据反馈完成一次实质修改")
            if evidence_ready and transfer_count < 1:
                next_required.append("换一份新材料完成迁移验证")
            if evidence_ready and verified_count < 1:
                next_required.append("获得至少一条人工或系统核验通过的规范 Evidence")

            sources = (event_sources[capability_id] + all_evidence[capability_id])[-12:]
            records.append(
                {
                    "capabilityId": capability_id,
                    "name": definition.get("name") or capability_id,
                    "plain": definition.get("plain") or "",
                    "verificationLevel": level,
                    "verificationVersion": VERIFICATION_VERSION,
                    "confidence": confidence,
                    "metrics": {
                        "distinctTaskContexts": distinct_task_count,
                        "foundationAttempts": attempts,
                        "guided": guided,
                        "independent": independent_count,
                        "revisionSuccesses": revision_count,
                        "transferSuccesses": transfer_count,
                        "verifiedEvidenceCount": verified_count,
                    },
                    "requirements": requirements,
                    "nextRequired": next_required,
                    "sources": sources,
                    "authority": "server",
                    "clientMayPromote": False,
                }
            )

        return {
            "version": VERIFICATION_VERSION,
            "levels": [LEVEL_UNOBSERVED, LEVEL_SIGNAL, LEVEL_EVIDENCE, LEVEL_VERIFIED],
            "policy": {
                "signal": "至少一次服务器可观察的实践信号",
                "evidence": "至少两个不同任务情境，并出现独立完成、实质修订或迁移信号",
                "verifiedEvidence": "达到 Evidence 后，还需迁移成功且至少一条规范 Evidence 核验通过",
                "clientAuthority": "read_only",
            },
            "summary": counts,
            "items": records,
        }
