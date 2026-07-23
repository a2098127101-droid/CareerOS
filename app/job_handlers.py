from __future__ import annotations

from typing import Any


def register_background_handlers(job_manager, *, knowledge_store) -> None:
    """Register deterministic worker-safe job handlers without importing the FastAPI app."""

    def knowledge_reindex(payload: dict[str, Any], progress):
        progress(10, "preparing knowledge index")
        result = knowledge_store.rebuild_hybrid_index(
            only_missing=bool(payload.get("only_missing", True)),
            tenant_id=payload.get("tenant_id") or None,
        )
        progress(90, "finalizing index")
        return result

    def runtime_probe(payload: dict[str, Any], progress):
        progress(50, "runtime certification probe")
        return {"marker": str(payload.get("marker") or ""), "worker_probe": True}

    job_manager.register("knowledge_reindex", knowledge_reindex)
    job_manager.register("runtime_probe", runtime_probe)
