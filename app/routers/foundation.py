from __future__ import annotations

from typing import Any, Callable
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..foundation_progress import FoundationError
from ..unified_runtime_store import RuntimeVersionConflict


class FoundationAnswerRequest(BaseModel):
    answer: dict[str, Any] = Field(default_factory=dict)


class ExpressionRequest(BaseModel):
    reflection: str = ""


def build_foundation_router(*, service: Any, sessions: Any, identity: Any, current_principal: Callable, canonical_role: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/foundation/v1", tags=["foundation-practice"])

    def role(p) -> str:
        return canonical_role(p.role)

    def can_access(p, user_id: str) -> bool:
        if not user_id or user_id == p.user_id:
            return True
        if p.is_super_admin or role(p) == "organization_admin":
            return True
        if role(p) == "advisor":
            return bool(identity.user_class_ids(p.user_id, p.tenant_id, role="teacher") & identity.user_class_ids(user_id, p.tenant_id, role="student"))
        return False

    def owner(p, requested: str = "") -> str:
        uid = (requested or p.user_id or "demo-local").strip()
        if not can_access(p, uid):
            raise HTTPException(status_code=403, detail="subject user access denied")
        return uid

    def ensure_session(p, uid: str, requested_session_id: str = ""):
        requested_session_id = (requested_session_id or "").strip()
        if requested_session_id:
            try:
                state = sessions.get(requested_session_id, tenant_id=p.tenant_id)
            except KeyError:
                raise HTTPException(status_code=404, detail="session not found")
            if str(getattr(state, "student_user_id", "") or "") != uid:
                raise HTTPException(status_code=403, detail="session owner mismatch")
            return state
        rows = sessions.list(limit=1, tenant_id=p.tenant_id, student_user_id=uid)
        if rows:
            return rows[0][0]
        groups = sorted(identity.user_class_ids(uid, p.tenant_id, role="student")) if uid else []
        return sessions.create(tenant_id=p.tenant_id, student_user_id=uid, class_id=(groups[0] if groups else "default"), student_id=uid)

    def invoke(fn):
        try:
            return fn()
        except FoundationError as exc:
            raise HTTPException(status_code=422, detail={"code": "foundation", "message": str(exc)})
        except RuntimeVersionConflict as exc:
            raise HTTPException(status_code=409, detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual})
        except KeyError:
            raise HTTPException(status_code=404, detail="foundation object not found")

    @router.get("/me")
    def me(subject_user_id: str = Query(default=""), session_id: str = Query(default=""), principal=Depends(current_principal)):
        uid = owner(principal, subject_user_id)
        session = ensure_session(principal, uid, session_id)
        return invoke(lambda: service.summary(tenant_id=principal.tenant_id, owner_user_id=uid, session_id=session.session_id))

    @router.get("/tasks/{task_id}")
    def task(task_id: str, subject_user_id: str = Query(default=""), session_id: str = Query(default=""), principal=Depends(current_principal)):
        uid = owner(principal, subject_user_id); session = ensure_session(principal, uid, session_id)
        return invoke(lambda: {"ok": True, **service.get_task(task_id, tenant_id=principal.tenant_id, owner_user_id=uid, session_id=session.session_id)})

    @router.put("/tasks/{task_id}/answer")
    def save(task_id: str, req: FoundationAnswerRequest, subject_user_id: str = Query(default=""), session_id: str = Query(default=""), principal=Depends(current_principal)):
        uid = owner(principal, subject_user_id); session = ensure_session(principal, uid, session_id)
        return invoke(lambda: {"ok": True, "state": service.save_answer(task_id, req.answer, tenant_id=principal.tenant_id, owner_user_id=uid, session_id=session.session_id, updated_by=principal.user_id or uid)})

    @router.post("/tasks/{task_id}/hint")
    def hint(task_id: str, subject_user_id: str = Query(default=""), session_id: str = Query(default=""), principal=Depends(current_principal)):
        uid = owner(principal, subject_user_id); session = ensure_session(principal, uid, session_id)
        return invoke(lambda: service.hint(task_id, tenant_id=principal.tenant_id, owner_user_id=uid, session_id=session.session_id, updated_by=principal.user_id or uid))

    @router.post("/tasks/{task_id}/complete")
    def complete(task_id: str, req: FoundationAnswerRequest, subject_user_id: str = Query(default=""), session_id: str = Query(default=""), principal=Depends(current_principal)):
        uid = owner(principal, subject_user_id); session = ensure_session(principal, uid, session_id)
        return invoke(lambda: service.complete_task(task_id, req.answer, tenant_id=principal.tenant_id, owner_user_id=uid, session_id=session.session_id, updated_by=principal.user_id or uid))

    @router.post("/expression")
    def expression(req: ExpressionRequest, subject_user_id: str = Query(default=""), session_id: str = Query(default=""), principal=Depends(current_principal)):
        uid = owner(principal, subject_user_id); session = ensure_session(principal, uid, session_id)
        return invoke(lambda: service.expression(req.reflection, tenant_id=principal.tenant_id, owner_user_id=uid, session_id=session.session_id, updated_by=principal.user_id or uid))

    @router.get("/growth/{subject_user_id}")
    def growth(subject_user_id: str, session_id: str = Query(default=""), principal=Depends(current_principal)):
        if not (principal.is_super_admin or role(principal) in {"organization_admin", "advisor"}):
            raise HTTPException(status_code=403, detail="staff role required")
        uid = owner(principal, subject_user_id); session = ensure_session(principal, uid, session_id)
        return invoke(lambda: service.teacher_growth(tenant_id=principal.tenant_id, owner_user_id=uid, session_id=session.session_id))

    @router.get("/cohort")
    def cohort(limit: int = Query(default=100, ge=1, le=500), principal=Depends(current_principal)):
        if not (principal.is_super_admin or role(principal) in {"organization_admin", "advisor"}):
            raise HTTPException(status_code=403, detail="staff role required")
        rows = sessions.list(limit=max(limit * 3, 100), tenant_id=principal.tenant_id)
        seen: set[str] = set()
        items: list[dict[str, Any]] = []
        for state, updated_at in rows:
            uid = str(getattr(state, "student_user_id", "") or "").strip()
            if not uid or uid in seen or not can_access(principal, uid):
                continue
            seen.add(uid)
            growth = invoke(lambda uid=uid, sid=state.session_id: service.teacher_growth(tenant_id=principal.tenant_id, owner_user_id=uid, session_id=sid))
            summary = growth.get("summary") or {}
            items.append({
                "userId": uid,
                "sessionId": state.session_id,
                "name": str(getattr(getattr(state, "profile", None), "name", "") or "") or uid,
                "completed": int(summary.get("completed") or 0),
                "total": int(summary.get("total") or 8),
                "progress": float(summary.get("progress") or 0),
                "foundationComplete": bool(summary.get("foundationComplete")),
                "professionalUnlocked": bool(summary.get("professionalUnlocked")),
                "currentTask": summary.get("currentTask"),
                "abilities": summary.get("abilities") or [],
                "updatedAt": updated_at,
            })
            if len(items) >= limit:
                break
        items.sort(key=lambda x: (x.get("foundationComplete", False), -float(x.get("progress") or 0), str(x.get("name") or "")))
        return {"ok": True, "items": items, "count": len(items)}

    return router
