from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..real_work_sample import RealWorkSampleError, RealWorkSampleService
from ..unified_runtime_store import RuntimeVersionConflict


class WorkSampleSubmission(BaseModel):
    priority_ticket_ids: list[str] = Field(default_factory=list, max_length=6)
    handoff: str = Field(default="", max_length=8000)
    work_notes: str = Field(default="", max_length=8000)


def build_work_sample_router(
    *,
    service: RealWorkSampleService,
    sessions: Any,
    identity: Any,
    current_principal: Callable,
    canonical_role: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/api/work-samples/v1", tags=["real-work-samples"])

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

    def invoke(fn):
        try:
            return fn()
        except RealWorkSampleError as exc:
            raise HTTPException(status_code=422, detail={"code": "real_work_sample", "message": str(exc)})
        except RuntimeVersionConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual},
            )

    @router.get("/active")
    def active(session_id: str = Query(default=""), principal=Depends(current_principal)):
        uid, sid = context(principal, session_id)
        return {
            "ok": True,
            "workSample": service.public_state(
                tenant_id=principal.tenant_id,
                owner_user_id=uid,
                session_id=sid,
            ),
        }

    @router.post("/start")
    def start(session_id: str = Query(default=""), principal=Depends(current_principal)):
        uid, sid = context(principal, session_id)
        return {
            "ok": True,
            "workSample": invoke(
                lambda: service.start(
                    tenant_id=principal.tenant_id,
                    owner_user_id=uid,
                    session_id=sid,
                    updated_by=uid,
                )
            ),
        }

    def submit(req: WorkSampleSubmission, principal, session_id: str, method: str):
        uid, sid = context(principal, session_id)
        fn = getattr(service, method)
        return invoke(
            lambda: fn(
                priority_ticket_ids=req.priority_ticket_ids,
                handoff=req.handoff,
                work_notes=req.work_notes,
                tenant_id=principal.tenant_id,
                owner_user_id=uid,
                session_id=sid,
                updated_by=uid,
            )
        )

    @router.post("/v1")
    def submit_v1(req: WorkSampleSubmission, session_id: str = Query(default=""), principal=Depends(current_principal)):
        return submit(req, principal, session_id, "submit_v1")

    @router.post("/v2")
    def submit_v2(req: WorkSampleSubmission, session_id: str = Query(default=""), principal=Depends(current_principal)):
        return submit(req, principal, session_id, "submit_v2")

    @router.post("/transfer")
    def submit_transfer(req: WorkSampleSubmission, session_id: str = Query(default=""), principal=Depends(current_principal)):
        return submit(req, principal, session_id, "submit_transfer")

    return router
