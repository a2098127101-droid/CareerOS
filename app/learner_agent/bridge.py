from __future__ import annotations

from typing import Any, Callable


class LearnerAgentEventBridge:
    """Thin server-event adapter.

    Domain actions must succeed even if the Agent observation layer is temporarily
    unavailable, so bridge failures are intentionally isolated from the business
    transaction that produced the event.
    """

    def __init__(self, runtime_provider: Callable[[], Any | None]):
        self.runtime_provider = runtime_provider

    def emit(self, **event: Any) -> dict[str, Any]:
        runtime = self.runtime_provider()
        if runtime is None:
            return {"accepted": False, "reason": "learner_agent_runtime_unavailable"}
        try:
            result = runtime.ingest_server_event(**event)
            return {"accepted": True, "result": result}
        except Exception as exc:
            return {"accepted": False, "reason": "learner_agent_observation_failed", "error": str(exc)[:240]}
