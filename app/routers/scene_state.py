from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from ..scene_state import SceneStateService


def build_scene_state_router(
    *,
    service: SceneStateService,
    sessions: Any,
    identity: Any,
    current_principal: Callable,
    canonical_role: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/api/scene/v1", tags=["scene-state"])

    def context(principal, requested_session_id: str = "") -> tuple[str, str]:
        if not principal.authenticated or canonical_role(principal.role) != "participant":
            raise HTTPException(status_code=403, detail="participant account required")
        uid = principal.user_id
        requested = str(requested_session_id or "").strip()
        if requested:
            try:
                state = sessions.get(requested, tenant_id=principal.tenant_id)
            except KeyError:
                raise HTTPException(status_code=404, detail="session not found")
            if str(getattr(state, "student_user_id", "") or "") != uid:
                raise HTTPException(status_code=403, detail="session owner mismatch")
            return uid, state.session_id
        rows = sessions.list(limit=1, tenant_id=principal.tenant_id, student_user_id=uid)
        if rows:
            return uid, rows[0][0].session_id
        groups = sorted(identity.user_class_ids(uid, principal.tenant_id, role="student"))
        state = sessions.create(
            tenant_id=principal.tenant_id,
            student_user_id=uid,
            class_id=(groups[0] if groups else "default"),
            student_id=uid,
        )
        return uid, state.session_id

    @router.get("/state")
    def scene_state(session_id: str = Query(default=""), principal=Depends(current_principal)):
        uid, sid = context(principal, session_id)
        return service.build(
            tenant_id=principal.tenant_id,
            owner_user_id=uid,
            session_id=sid,
            identity={
                "userId": uid,
                "displayName": principal.display_name,
                "role": canonical_role(principal.role),
                "tenantId": principal.tenant_id,
            },
        )

    @router.get("/contract")
    def contract(principal=Depends(current_principal)):
        if not principal.authenticated:
            raise HTTPException(status_code=401, detail="authentication required")
        return {
            "ok": True,
            "sceneStateVersion": "1.0",
            "authority": "server",
            "readOnly": True,
            "capabilityLevels": ["unobserved", "signal", "evidence", "verified_evidence"],
            "clientMayPromoteCapability": False,
            "clientMayVerifyEvidence": False,
            "allowedClientEffects": ["focus", "inspect", "filter", "camera", "animation"],
        }

    return router
