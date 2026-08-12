from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..unified_runtime_store import RuntimeVersionConflict


class LearnerAgentMemory:
    ENTITY_TYPE = "learner_agent_memory"
    ENTITY_ID = "stepin-learner-memory"
    MAX_EVENTS = 120

    def __init__(self, repository: Any):
        self.repository = repository

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _default(owner_user_id: str, session_id: str) -> dict[str, Any]:
        return {
            "id": LearnerAgentMemory.ENTITY_ID,
            "ownerUserId": owner_user_id,
            "sessionId": session_id,
            "events": [],
            "diagnosisCounts": {},
            "actionCounts": {},
            "patterns": {},
            "updatedAt": LearnerAgentMemory._now(),
        }

    def load(self, *, tenant_id: str, owner_user_id: str, session_id: str) -> dict[str, Any]:
        try:
            return self.repository.get(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                entity_id=self.ENTITY_ID,
                owner_user_id=owner_user_id,
            )
        except KeyError:
            return self.repository.upsert(
                tenant_id=tenant_id,
                entity_type=self.ENTITY_TYPE,
                entity_id=self.ENTITY_ID,
                owner_user_id=owner_user_id,
                updated_by=owner_user_id,
                payload=self._default(owner_user_id, session_id),
            )

    def record(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        kind: str,
        payload: dict[str, Any],
        updated_by: str,
    ) -> dict[str, Any]:
        for _attempt in range(2):
            memory = self.load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
            version = int(memory.get("_version") or 1)
            events = list(memory.get("events") or [])
            event = {
                "seq": int(events[-1].get("seq") or 0) + 1 if events else 1,
                "kind": kind,
                "at": self._now(),
                **dict(payload or {}),
            }
            events.append(event)
            memory["events"] = events[-self.MAX_EVENTS :]
            diagnosis = str(event.get("diagnosis") or "")
            action = str(event.get("action") or "")
            if diagnosis:
                counts = dict(memory.get("diagnosisCounts") or {})
                counts[diagnosis] = int(counts.get(diagnosis) or 0) + 1
                memory["diagnosisCounts"] = counts
                if diagnosis not in {"SUCCESS", "PROGRESS"}:
                    patterns = dict(memory.get("patterns") or {})
                    row = dict(patterns.get(diagnosis) or {})
                    row["count"] = int(row.get("count") or 0) + 1
                    row["lastSeenAt"] = event["at"]
                    row["taskId"] = str(event.get("taskId") or row.get("taskId") or "")
                    patterns[diagnosis] = row
                    memory["patterns"] = patterns
            if action:
                counts = dict(memory.get("actionCounts") or {})
                counts[action] = int(counts.get(action) or 0) + 1
                memory["actionCounts"] = counts
            memory["updatedAt"] = event["at"]
            clean = {k: v for k, v in memory.items() if not k.startswith("_") and k != "entity_type"}
            try:
                return self.repository.upsert(
                    tenant_id=tenant_id,
                    entity_type=self.ENTITY_TYPE,
                    entity_id=self.ENTITY_ID,
                    owner_user_id=owner_user_id,
                    updated_by=updated_by,
                    expected_version=version,
                    payload=clean,
                )
            except RuntimeVersionConflict:
                if _attempt:
                    raise
        raise RuntimeError("unreachable")

    def recent(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        limit: int = 20,
        kind: str = "",
    ) -> list[dict[str, Any]]:
        memory = self.load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        rows = list(memory.get("events") or [])
        if kind:
            rows = [row for row in rows if str(row.get("kind") or "") == kind]
        return rows[-max(1, min(int(limit), self.MAX_EVENTS)) :]

    def snapshot(self, *, tenant_id: str, owner_user_id: str, session_id: str, limit: int = 30) -> dict[str, Any]:
        memory = self.load(tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id)
        return {
            "events": list(memory.get("events") or [])[-max(1, min(limit, self.MAX_EVENTS)) :],
            "diagnosisCounts": dict(memory.get("diagnosisCounts") or {}),
            "actionCounts": dict(memory.get("actionCounts") or {}),
            "patterns": dict(memory.get("patterns") or {}),
            "updatedAt": memory.get("updatedAt") or "",
        }
