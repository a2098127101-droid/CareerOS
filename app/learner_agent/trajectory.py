from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TrajectoryEventType(str, Enum):
    USER_MESSAGE = "user_message"
    ANSWER_SAVED = "answer_saved"
    TASK_FAILED = "task_failed"
    TASK_COMPLETED = "task_completed"
    HINT_REQUESTED = "hint_requested"
    REVISION_REQUESTED = "revision_requested"
    REVISION_SUBMITTED = "revision_submitted"
    EXPRESSION_SUBMITTED = "expression_submitted"
    TRANSFER_FAILED = "transfer_failed"
    TRANSFER_COMPLETED = "transfer_completed"
    TEACHER_FEEDBACK = "teacher_feedback"
    TEACHER_FEEDBACK_RESOLVED = "teacher_feedback_resolved"
    EVIDENCE_VERIFIED = "evidence_verified"
    EVIDENCE_PARTIAL = "evidence_partial"
    EVIDENCE_REJECTED = "evidence_rejected"
    HUMAN_REVIEW_RESOLVED = "human_review_resolved"
    PROJECT_STARTED = "project_started"
    PROJECT_UPDATED = "project_updated"
    PROJECT_MILESTONE = "project_milestone"
    PROJECT_COMPLETED = "project_completed"
    AGENT_INTERVENTION = "agent_intervention"


class TrajectoryEvent(BaseModel):
    event_id: str
    event_type: str
    source: str
    tenant_id: str
    owner_user_id: str
    session_id: str
    actor_user_id: str = ""
    task_id: str = ""
    project_id: str = ""
    evidence_id: str = ""
    claim_id: str = ""
    outcome: str = "neutral"
    correlation_id: str = ""
    intervention_id: str = ""
    policy_version: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: str


class LearnerTrajectoryStore:
    """Append-oriented, tenant/owner-scoped learner trajectory.

    Memory is intentionally short and conversational; trajectory is the longer-lived
    audit/training surface. One runtime entity is written per event so later calibration
    can inspect complete sequences without coupling to a browser or LLM transcript.
    """

    ENTITY_TYPE = "learner_trajectory_event"
    MAX_QUERY_EVENTS = 5000

    def __init__(self, repository: Any):
        self.repository = repository

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _clip(value: Any, *, depth: int = 0) -> Any:
        if depth > 3:
            return "[truncated]"
        if isinstance(value, str):
            return value[:2000]
        if isinstance(value, dict):
            return {
                str(k)[:80]: LearnerTrajectoryStore._clip(v, depth=depth + 1)
                for k, v in list(value.items())[:50]
                if str(k) not in {"password", "token", "access_token", "api_key", "secret"}
            }
        if isinstance(value, list):
            return [LearnerTrajectoryStore._clip(v, depth=depth + 1) for v in value[:50]]
        if isinstance(value, (int, float, bool)) or value is None:
            return value
        return str(value)[:1000]

    @staticmethod
    def _event_id(idempotency_key: str = "") -> str:
        if idempotency_key:
            digest = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:24].upper()
            return f"TRJ-{digest}"
        return f"TRJ-{uuid4().hex[:24].upper()}"

    def record(
        self,
        *,
        event_type: str,
        source: str,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        actor_user_id: str = "",
        task_id: str = "",
        project_id: str = "",
        evidence_id: str = "",
        claim_id: str = "",
        outcome: str = "neutral",
        correlation_id: str = "",
        intervention_id: str = "",
        policy_version: str = "",
        payload: dict[str, Any] | None = None,
        idempotency_key: str = "",
        updated_by: str = "",
    ) -> dict[str, Any]:
        event_id = self._event_id(idempotency_key)
        event = TrajectoryEvent(
            event_id=event_id,
            event_type=str(event_type or TrajectoryEventType.USER_MESSAGE.value)[:80],
            source=str(source or "unknown")[:80],
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            actor_user_id=str(actor_user_id or "")[:160],
            task_id=str(task_id or "")[:180],
            project_id=str(project_id or "")[:180],
            evidence_id=str(evidence_id or "")[:180],
            claim_id=str(claim_id or "")[:180],
            outcome=(str(outcome or "neutral")[:24] if outcome in {"success", "failure", "neutral"} else "neutral"),
            correlation_id=str(correlation_id or "")[:180],
            intervention_id=str(intervention_id or "")[:180],
            policy_version=str(policy_version or "")[:80],
            payload=self._clip(payload or {}),
            occurred_at=self._now(),
        )
        try:
            existing = self.repository.get(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                entity_id=event_id,
                owner_user_id=owner_user_id,
            )
            return existing
        except KeyError:
            return self.repository.upsert(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                entity_id=event_id,
                owner_user_id=owner_user_id,
                updated_by=updated_by or actor_user_id or owner_user_id,
                payload=event.model_dump(mode="json"),
            )

    def list_events(
        self,
        *,
        tenant_id: str,
        owner_user_id: str | None = None,
        session_id: str = "",
        event_types: set[str] | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        cap = max(1, min(int(limit), self.MAX_QUERY_EVENTS))
        if hasattr(self.repository, "list_all"):
            rows = self.repository.list_all(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                owner_user_id=owner_user_id,
                include_deleted=False,
            )
        elif hasattr(self.repository, "list"):
            rows = self.repository.list(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                owner_user_id=owner_user_id,
                limit=self.MAX_QUERY_EVENTS,
                include_deleted=False,
            )
        else:
            # Lightweight unit-test repositories may intentionally expose only get/upsert.
            rows = []
        if session_id:
            rows = [row for row in rows if str(row.get("session_id") or "") == session_id]
        if event_types:
            rows = [row for row in rows if str(row.get("event_type") or "") in event_types]
        rows.sort(key=lambda row: (int(row.get("_revision") or 0), str(row.get("occurred_at") or ""), str(row.get("event_id") or "")))
        return rows[-cap:]

    def summary(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        limit: int = 2000,
    ) -> dict[str, Any]:
        rows = self.list_events(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            limit=limit,
        )
        counts = Counter(str(row.get("event_type") or "") for row in rows)
        outcomes = Counter(str(row.get("outcome") or "neutral") for row in rows)
        return {
            "events": len(rows),
            "eventTypeCounts": dict(counts),
            "outcomeCounts": dict(outcomes),
            "lastEventId": str((rows[-1] if rows else {}).get("event_id") or ""),
            "lastEventAt": str((rows[-1] if rows else {}).get("occurred_at") or ""),
        }
