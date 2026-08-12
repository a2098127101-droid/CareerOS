from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from .trajectory import LearnerTrajectoryStore


class LearnerAgentPolicyProfile(BaseModel):
    profile_id: str = "default"
    version: str = "2.2-default"
    status: str = "default"
    ask_until_failure: int = 1
    hint_at_failure: int = 2
    explain_until_failure: int = 3
    request_evidence_at_failure: int = 4
    escalate_at_failure: int = 5
    min_samples: int = 30
    source_event_count: int = 0
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: str = ""
    activated_at: str = ""


class LearnerAgentCalibrationService:
    """Trajectory-based calibration with human-controlled activation.

    Safety constraints are not learned. Calibration may only tune when pedagogical
    support escalates; it never enables final-answer generation, bypasses gates, or
    changes answer-leakage policy. Small cohorts produce metrics but no candidate.
    """

    ENTITY_TYPE = "learner_agent_policy_profile"
    ACTIVE_ID = "active"
    OWNER = "__tenant_policy__"

    def __init__(self, repository: Any, trajectory: LearnerTrajectoryStore):
        self.repository = repository
        self.trajectory = trajectory

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def default_profile(cls) -> LearnerAgentPolicyProfile:
        return LearnerAgentPolicyProfile(created_at=cls._now())

    def active_profile(self, *, tenant_id: str) -> LearnerAgentPolicyProfile:
        try:
            row = self.repository.get(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                entity_id=self.ACTIVE_ID,
                owner_user_id=self.OWNER,
            )
            clean = {k: v for k, v in row.items() if not k.startswith("_") and k != "entity_type"}
            return LearnerAgentPolicyProfile.model_validate(clean)
        except KeyError:
            return self.default_profile()

    @staticmethod
    def _challenge_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            task_id = str(row.get("task_id") or "")
            if not task_id:
                continue
            groups[(str(row.get("owner_user_id") or ""), str(row.get("session_id") or ""), task_id)].append(row)
        challenge = Counter()
        attempts = successes = failures = hints = 0
        for events in groups.values():
            failed = sum(1 for e in events if e.get("event_type") in {"task_failed", "transfer_failed"})
            success = any(e.get("event_type") in {"task_completed", "revision_submitted", "transfer_completed", "project_completed"} and e.get("outcome") != "failure" for e in events)
            support = sum(1 for e in events if e.get("event_type") == "hint_requested" or (e.get("event_type") == "agent_intervention" and str((e.get("payload") or {}).get("action") or "") in {"HINT", "EXPLAIN", "REQUEST_EVIDENCE", "ESCALATE"}))
            attempts += failed + (1 if success else 0)
            successes += 1 if success else 0
            failures += failed
            hints += sum(1 for e in events if e.get("event_type") == "hint_requested")
            if not success and failed >= 3:
                challenge["over_challenged"] += 1
            elif success and failed == 0 and support == 0:
                challenge["under_challenged"] += 1
            elif success and failed <= 2 and support <= 2:
                challenge["optimally_challenged"] += 1
            elif failed >= 3 or support >= 3:
                challenge["over_challenged"] += 1
            else:
                challenge["optimally_challenged"] += 1
        total_groups = sum(challenge.values())
        return {
            "taskGroups": len(groups),
            "attempts": attempts,
            "successes": successes,
            "failures": failures,
            "hints": hints,
            "immediateSuccessRate": round(challenge.get("under_challenged", 0) / total_groups, 4) if total_groups else 0.0,
            "optimalChallengeRate": round(challenge.get("optimally_challenged", 0) / total_groups, 4) if total_groups else 0.0,
            "overChallengeRate": round(challenge.get("over_challenged", 0) / total_groups, 4) if total_groups else 0.0,
            "hintDependencyRate": round(hints / max(1, attempts), 4),
            "challengeDistribution": dict(challenge),
        }

    @staticmethod
    def _intervention_effectiveness(rows: list[dict[str, Any]]) -> dict[str, Any]:
        by_action: dict[str, dict[str, int]] = defaultdict(lambda: {"observed": 0, "successWithinNext3": 0})
        for idx, row in enumerate(rows):
            if row.get("event_type") != "agent_intervention":
                continue
            action = str((row.get("payload") or {}).get("action") or "")
            if not action:
                continue
            by_action[action]["observed"] += 1
            task_id = str(row.get("task_id") or "")
            owner = str(row.get("owner_user_id") or "")
            for later in rows[idx + 1 : idx + 4]:
                if owner and str(later.get("owner_user_id") or "") != owner:
                    continue
                if task_id and str(later.get("task_id") or "") not in {"", task_id}:
                    continue
                if later.get("event_type") in {"task_completed", "revision_submitted", "transfer_completed", "project_completed"} and later.get("outcome") != "failure":
                    by_action[action]["successWithinNext3"] += 1
                    break
                if later.get("event_type") in {"task_failed", "transfer_failed"}:
                    break
        out: dict[str, Any] = {}
        for action, stats in by_action.items():
            observed = stats["observed"]
            out[action] = {
                **stats,
                "shortHorizonRecoveryRate": round(stats["successWithinNext3"] / observed, 4) if observed else 0.0,
            }
        return out

    def analyze(
        self,
        *,
        tenant_id: str,
        owner_user_id: str | None = None,
        session_id: str = "",
        limit: int = 5000,
    ) -> dict[str, Any]:
        rows = self.trajectory.list_events(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            limit=limit,
        )
        counts = Counter(str(row.get("event_type") or "") for row in rows)
        challenge = self._challenge_metrics(rows)
        interventions = self._intervention_effectiveness(rows)
        transfers = counts.get("transfer_completed", 0) + counts.get("transfer_failed", 0)
        evidence_total = counts.get("evidence_verified", 0) + counts.get("evidence_partial", 0) + counts.get("evidence_rejected", 0)
        feedback_total = counts.get("teacher_feedback", 0)
        labels = [row for row in rows if row.get("event_type") == "human_review_resolved" and isinstance(row.get("payload"), dict)]
        diagnostic_labels = [row for row in labels if (row.get("payload") or {}).get("diagnosisCorrect") is not None]
        diagnostic_agree = sum(1 for row in diagnostic_labels if bool((row.get("payload") or {}).get("diagnosisCorrect")))
        return {
            "eventCount": len(rows),
            "eventTypeCounts": dict(counts),
            **challenge,
            "transferSuccessRate": round(counts.get("transfer_completed", 0) / transfers, 4) if transfers else 0.0,
            "evidenceVerifiedRate": round(counts.get("evidence_verified", 0) / evidence_total, 4) if evidence_total else 0.0,
            "feedbackResolutionRate": round(counts.get("teacher_feedback_resolved", 0) / feedback_total, 4) if feedback_total else 0.0,
            "revisionAfterFeedbackRate": round(counts.get("revision_submitted", 0) / feedback_total, 4) if feedback_total else 0.0,
            "humanLabelCount": len(labels),
            "diagnosisLabelCount": len(diagnostic_labels),
            "diagnosisAgreementRate": round(diagnostic_agree / len(diagnostic_labels), 4) if diagnostic_labels else None,
            "interventionEffectiveness": interventions,
        }

    def build_candidate(self, *, tenant_id: str, min_samples: int = 30, updated_by: str = "system") -> dict[str, Any]:
        metrics = self.analyze(tenant_id=tenant_id, owner_user_id=None, limit=LearnerTrajectoryStore.MAX_QUERY_EVENTS)
        samples = int(metrics.get("attempts") or 0)
        if samples < max(10, int(min_samples)):
            return {
                "ok": True,
                "status": "insufficient_data",
                "requiredSamples": max(10, int(min_samples)),
                "observedSamples": samples,
                "metrics": metrics,
                "candidate": None,
            }
        hint_at = 2
        if float(metrics.get("immediateSuccessRate") or 0) >= 0.65 and float(metrics.get("hintDependencyRate") or 0) >= 0.25:
            hint_at = 3
        over = float(metrics.get("overChallengeRate") or 0)
        explain_until = max(3, hint_at + 1)
        evidence_at = explain_until + 1
        escalate_at = evidence_at + 1
        if over >= 0.30:
            escalate_at = max(evidence_at + 1, 5)
        elif over <= 0.10:
            escalate_at = min(6, evidence_at + 2)
        candidate = LearnerAgentPolicyProfile(
            profile_id=f"candidate-{uuid4().hex[:12]}",
            version=f"2.2-cal-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            status="candidate",
            ask_until_failure=1,
            hint_at_failure=hint_at,
            explain_until_failure=explain_until,
            request_evidence_at_failure=evidence_at,
            escalate_at_failure=escalate_at,
            min_samples=max(10, int(min_samples)),
            source_event_count=int(metrics.get("eventCount") or 0),
            metrics=metrics,
            created_at=self._now(),
        )
        self.repository.upsert(
            tenant_id=tenant_id,
            entity_type=self.ENTITY_TYPE,
            entity_id=candidate.profile_id,
            owner_user_id=self.OWNER,
            updated_by=updated_by,
            payload=candidate.model_dump(mode="json"),
        )
        return {"ok": True, "status": "candidate", "metrics": metrics, "candidate": candidate.model_dump(mode="json")}

    def activate(self, candidate_id: str, *, tenant_id: str, updated_by: str) -> LearnerAgentPolicyProfile:
        raw = self.repository.get(
            tenant_id=tenant_id,
            entity_type=self.ENTITY_TYPE,
            entity_id=candidate_id,
            owner_user_id=self.OWNER,
        )
        clean = {k: v for k, v in raw.items() if not k.startswith("_") and k != "entity_type"}
        candidate = LearnerAgentPolicyProfile.model_validate(clean)
        if candidate.status != "candidate" or candidate.source_event_count < candidate.min_samples:
            raise ValueError("calibration candidate is not eligible for activation")
        candidate.status = "active"
        candidate.activated_at = self._now()
        saved = self.repository.upsert(
            tenant_id=tenant_id,
            entity_type=self.ENTITY_TYPE,
            entity_id=self.ACTIVE_ID,
            owner_user_id=self.OWNER,
            updated_by=updated_by,
            payload={**candidate.model_dump(mode="json"), "profile_id": self.ACTIVE_ID},
        )
        return LearnerAgentPolicyProfile.model_validate({k: v for k, v in saved.items() if not k.startswith("_") and k != "entity_type"})
