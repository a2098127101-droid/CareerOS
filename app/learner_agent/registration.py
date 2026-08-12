from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..foundation_progress import FoundationError
from ..unified_runtime_store import RuntimeVersionConflict
from .models import AgentEvaluationRequest, AgentObservationRequest, AgentStepRequest
from .runtime import LearnerAgentRuntime


def register_learner_agent_routes(
    app: Any,
    *,
    foundation: Any,
    repository: Any,
    collaboration: Any,
    career_agents: Any,
    sessions: Any,
    identity: Any,
    current_principal: Any,
    canonical_role: Any,
) -> LearnerAgentRuntime:
    if getattr(app.state, "stepin_learner_agent_registered", False):
        return app.state.stepin_learner_agent

    runtime = LearnerAgentRuntime(
        repository=repository,
        foundation=foundation,
        collaboration=collaboration,
        career_agents=career_agents,
    )
    router = APIRouter(prefix="/api/learner-agent/v1", tags=["learner-agent"])

    def role(p) -> str:
        return canonical_role(p.role)

    def can_read(p, user_id: str) -> bool:
        if not user_id or user_id == p.user_id:
            return True
        if p.is_super_admin or role(p) == "organization_admin":
            return True
        if role(p) == "advisor":
            teacher_classes = identity.user_class_ids(p.user_id, p.tenant_id, role="teacher")
            student_classes = identity.user_class_ids(user_id, p.tenant_id, role="student")
            return bool(teacher_classes & student_classes)
        return False

    def resolve_subject(p, requested: str, *, write: bool) -> str:
        uid = str(requested or p.user_id or "").strip()
        if not uid:
            raise HTTPException(status_code=401, detail="authenticated user required")
        if write and (not p.authenticated or role(p) != "participant" or uid != p.user_id):
            raise HTTPException(status_code=403, detail="participant self-write required")
        if not can_read(p, uid):
            raise HTTPException(status_code=403, detail="subject user access denied")
        return uid

    def resolve_session(p, uid: str, requested: str, *, write: bool):
        requested = str(requested or "").strip()
        if requested:
            try:
                state = sessions.get(requested, tenant_id=p.tenant_id)
            except KeyError:
                raise HTTPException(status_code=404, detail="session not found")
            if str(getattr(state, "student_user_id", "") or "") != uid:
                raise HTTPException(status_code=403, detail="session owner mismatch")
            return state
        rows = sessions.list(limit=1, tenant_id=p.tenant_id, student_user_id=uid)
        if rows:
            return rows[0][0]
        if not write or uid != p.user_id:
            raise HTTPException(status_code=404, detail="student session not found")
        groups = sorted(identity.user_class_ids(uid, p.tenant_id, role="student"))
        return sessions.create(
            tenant_id=p.tenant_id,
            student_user_id=uid,
            class_id=(groups[0] if groups else "default"),
            student_id=uid,
        )

    def context(p, subject_user_id: str, session_id: str, *, write: bool):
        uid = resolve_subject(p, subject_user_id, write=write)
        session = resolve_session(p, uid, session_id, write=write)
        return uid, session.session_id

    def invoke(fn):
        try:
            return fn()
        except FoundationError as exc:
            raise HTTPException(status_code=422, detail={"code": "foundation", "message": str(exc)})
        except RuntimeVersionConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual},
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="learner agent object not found")

    @router.get("/manifest")
    def manifest(principal=Depends(current_principal)):
        if not principal.authenticated:
            raise HTTPException(status_code=401, detail="authentication required")
        return {"ok": True, **runtime.manifest(), "tools": runtime.tools.manifest()}

    @router.get("/tools")
    def tools(principal=Depends(current_principal)):
        if not principal.authenticated:
            raise HTTPException(status_code=401, detail="authentication required")
        return {"ok": True, "items": runtime.tools.manifest()}

    @router.get("/state")
    def state(
        subject_user_id: str = Query(default=""),
        session_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        uid, sid = context(principal, subject_user_id, session_id, write=False)
        value = invoke(lambda: runtime.get_state(tenant_id=principal.tenant_id, owner_user_id=uid, session_id=sid))
        return {"ok": True, "state": value.model_dump(mode="json")}

    @router.get("/memory")
    def memory(
        subject_user_id: str = Query(default=""),
        session_id: str = Query(default=""),
        limit: int = Query(default=30, ge=1, le=120),
        principal=Depends(current_principal),
    ):
        uid, sid = context(principal, subject_user_id, session_id, write=False)
        return {
            "ok": True,
            "memory": runtime.memory.snapshot(
                tenant_id=principal.tenant_id,
                owner_user_id=uid,
                session_id=sid,
                limit=limit,
            ),
        }

    @router.get("/decisions")
    def decisions(
        subject_user_id: str = Query(default=""),
        session_id: str = Query(default=""),
        limit: int = Query(default=20, ge=1, le=120),
        principal=Depends(current_principal),
    ):
        uid, sid = context(principal, subject_user_id, session_id, write=False)
        rows = runtime.memory.recent(
            tenant_id=principal.tenant_id,
            owner_user_id=uid,
            session_id=sid,
            limit=limit,
            kind="decision",
        )
        return {"ok": True, "items": rows}

    @router.post("/observe")
    def observe(
        req: AgentObservationRequest,
        session_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        uid, sid = context(principal, "", session_id, write=True)
        return invoke(
            lambda: runtime.observe(
                req,
                tenant_id=principal.tenant_id,
                owner_user_id=uid,
                session_id=sid,
                updated_by=principal.user_id,
            )
        )

    @router.post("/step")
    async def step(
        req: AgentStepRequest,
        session_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        uid, sid = context(principal, "", session_id, write=True)
        try:
            return await runtime.step(
                req,
                tenant_id=principal.tenant_id,
                owner_user_id=uid,
                session_id=sid,
                updated_by=principal.user_id,
            )
        except FoundationError as exc:
            raise HTTPException(status_code=422, detail={"code": "foundation", "message": str(exc)})
        except RuntimeVersionConflict as exc:
            raise HTTPException(
                status_code=409,
                detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual},
            )

    @router.post("/evaluate")
    def evaluate(
        req: AgentEvaluationRequest,
        subject_user_id: str = Query(default=""),
        session_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        uid, sid = context(principal, subject_user_id, session_id, write=False)
        aggregate = invoke(
            lambda: runtime.evaluation_report(
                tenant_id=principal.tenant_id,
                owner_user_id=uid,
                session_id=sid,
            )
        )
        local = None
        if req.output_text and req.action is not None:
            local = runtime.evaluator.evaluate_output(
                action=req.action,
                output_text=req.output_text,
                task_id=req.task_id,
            )
        return {"ok": True, "aggregate": aggregate, "sample": local}

    app.include_router(router)
    app.state.stepin_learner_agent = runtime
    app.state.stepin_learner_agent_registered = True
    return runtime
