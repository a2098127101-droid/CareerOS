from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import CapabilityState, LearnerAgentState


class LearnerAgentStateStore:
    ENTITY_TYPE = "learner_agent_state"
    ENTITY_ID = "stepin-learner"

    def __init__(self, repository: Any):
        self.repository = repository

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def load(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> tuple[LearnerAgentState, int | None]:
        try:
            raw = self.repository.get(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                entity_id=self.ENTITY_ID,
                owner_user_id=owner_user_id,
            )
            version = int(raw.get("_version") or 1)
            data = {k: v for k, v in raw.items() if not k.startswith("_") and k != "entity_type"}
            state = LearnerAgentState.model_validate(data)
        except KeyError:
            state = LearnerAgentState(owner_user_id=owner_user_id, session_id=session_id, updated_at=self._now())
            saved = self.repository.upsert(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                entity_id=self.ENTITY_ID,
                owner_user_id=owner_user_id,
                updated_by=owner_user_id,
                payload=state.model_dump(mode="json"),
            )
            version = int(saved.get("_version") or 1)
        if not state.session_id and session_id:
            state.session_id = session_id
        return state, version

    def save(
        self,
        state: LearnerAgentState,
        *,
        tenant_id: str,
        owner_user_id: str,
        updated_by: str,
        expected_version: int | None,
    ) -> tuple[LearnerAgentState, int]:
        state.updated_at = self._now()
        saved = self.repository.upsert(
            tenant_id=tenant_id,
            entity_type=self.ENTITY_TYPE,
            entity_id=self.ENTITY_ID,
            owner_user_id=owner_user_id,
            updated_by=updated_by,
            expected_version=expected_version,
            payload=state.model_dump(mode="json"),
        )
        version = int(saved.get("_version") or 1)
        data = {k: v for k, v in saved.items() if not k.startswith("_") and k != "entity_type"}
        return LearnerAgentState.model_validate(data), version

    @staticmethod
    def _capability_state(row: dict[str, Any]) -> CapabilityState:
        attempts = int(row.get("attempts") or 0)
        independent = int(row.get("independent") or 0)
        transfer = int(row.get("transfer") or 0)
        combined = int(row.get("combined") or 0)
        verified = int(row.get("laterVerifiedCount") or row.get("later_verified_count") or 0)
        average = float(row.get("average") or 0.0)
        confidence = min(
            0.95,
            (0.10 if attempts else 0.0)
            + 0.25 * max(0.0, min(1.0, average))
            + 0.25 * min(independent, 2) / 2
            + 0.25 * min(transfer + combined, 2) / 2
            + 0.15 * min(verified, 2) / 2,
        )
        if verified >= 2 and (transfer + combined) >= 1:
            stage = "verified"
        elif transfer + combined > 0:
            stage = "transfer"
        elif independent > 0:
            stage = "independent"
        elif attempts > 0:
            stage = "developing"
        else:
            stage = "unobserved"
        return CapabilityState(
            capability_id=str(row.get("id") or ""),
            label=str(row.get("name") or row.get("id") or ""),
            stage=stage,
            confidence=round(confidence, 3),
            attempts=attempts,
            independent=independent,
            transfer=transfer,
            combined=combined,
            later_verified_count=verified,
        )

    def sync_from_foundation(self, state: LearnerAgentState, summary: dict[str, Any]) -> LearnerAgentState:
        state.stage = str(summary.get("mode") or ("professional_ready" if summary.get("professionalUnlocked") else "beginner"))
        current = summary.get("currentTask") or ((summary.get("exploration") or {}).get("next") or {})
        state.current_task_id = str(current.get("id") or "")
        state.current_capability_ids = [str(x) for x in (current.get("abilities") or [])]
        state.capability_states = {
            str(row.get("id")): self._capability_state(row)
            for row in (summary.get("abilities") or [])
            if row.get("id")
        }
        return state
