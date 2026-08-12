from __future__ import annotations

import os
import sys
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .domain.roles import canonical_role
from .foundation_progress import FoundationError, FoundationProgressService
from .foundation_production import ExplorationRequest, ProductionFoundationFacade
from .routers.foundation import build_foundation_router
from .unified_runtime_store import RuntimeVersionConflict


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def register_foundation_production_routes(app) -> None:
    """Attach StepIn Foundation to the repositories already selected by production.

    Foundation is enabled for real production participants by default. Historical
    demo/compatibility environments keep the existing project flow unless
    ``STEPIN_FOUNDATION_DEMO_GATE=true`` is explicitly set. This gives production
    a practice-first beginner path without rewriting long-standing demo/API
    fixtures or existing professional projects.
    """
    if getattr(app.state, "stepin_foundation_registered", False):
        return
    main = sys.modules.get("app.main")
    if main is None:
        raise RuntimeError("app.main must be initialized before Foundation registration")

    base_service = FoundationProgressService(
        repository=main.unified_runtime_store,
        evidence=main.evidence_store,
        artifacts=main.artifact_store,
    )
    service = ProductionFoundationFacade(base_service)

    app.include_router(
        build_foundation_router(
            service=service,
            sessions=main.store,
            identity=main.auth_store,
            current_principal=main.current_principal,
            canonical_role=main.canonical_role,
        )
    )

    exploration_router = APIRouter(prefix="/api/foundation/v1", tags=["foundation-practice"])

    def participant_context(principal):
        if not principal.authenticated or canonical_role(principal.role) != "participant":
            raise HTTPException(status_code=403, detail="participant account required")
        rows = main.store.list(limit=1, tenant_id=principal.tenant_id, student_user_id=principal.user_id)
        state = rows[0][0] if rows else main._create_session_for_principal(principal)
        return principal.user_id, state.session_id

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
            raise HTTPException(status_code=404, detail="foundation object not found")

    @exploration_router.get("/explorations/{kind}")
    def exploration_task(kind: str, principal=Depends(main.current_principal)):
        uid, session_id = participant_context(principal)
        return invoke(
            lambda: service.exploration_task(
                kind,
                tenant_id=principal.tenant_id,
                owner_user_id=uid,
                session_id=session_id,
            )
        )

    @exploration_router.post("/explorations/{kind}/complete")
    def exploration_complete(kind: str, req: ExplorationRequest, principal=Depends(main.current_principal)):
        uid, session_id = participant_context(principal)
        return invoke(
            lambda: service.complete_exploration(
                kind,
                req.answer,
                tenant_id=principal.tenant_id,
                owner_user_id=uid,
                session_id=session_id,
                updated_by=uid,
            )
        )

    app.include_router(exploration_router)

    def principal_from_request(request: Request):
        token = request.cookies.get(main.AUTH_COOKIE)
        return main.auth_store.resolve_session(token)

    def gate_enabled() -> bool:
        if _truthy(os.getenv("STEPIN_FOUNDATION_DISABLED")):
            return False
        if bool(main.settings.demo_mode):
            return _truthy(os.getenv("STEPIN_FOUNDATION_DEMO_GATE"))
        return True

    def foundation_summary_for(principal):
        rows = main.store.list(limit=1, tenant_id=principal.tenant_id, student_user_id=principal.user_id)
        state = rows[0][0] if rows else main._create_session_for_principal(principal)
        return service.summary(
            tenant_id=principal.tenant_id,
            owner_user_id=principal.user_id,
            session_id=state.session_id,
        )

    def existing_projects(principal) -> list[dict[str, Any]]:
        try:
            return main.project_repository.list_projects(
                tenant_id=principal.tenant_id,
                owner_user_id=principal.user_id,
            )
        except Exception:
            return []

    @app.middleware("http")
    async def foundation_beginner_gate(request: Request, call_next):
        path = request.url.path.rstrip("/") or "/"
        principal = principal_from_request(request)
        if gate_enabled() and principal and canonical_role(principal.role) == "participant":
            # Existing professional work remains available to protect backwards compatibility.
            if not existing_projects(principal):
                summary = foundation_summary_for(principal)
                unlocked = bool(summary.get("professionalUnlocked"))
                if path in {"/projects", "/projects/new", "/student", "/participant"} and not unlocked:
                    return RedirectResponse(url="/static/foundation.html", status_code=302)
                if path == "/static/foundation.html" and unlocked:
                    return RedirectResponse(url="/projects", status_code=302)
                if path == "/api/v1/me/next-action" and request.method == "GET" and not unlocked:
                    mode = str(summary.get("mode") or "beginner")
                    current = summary.get("currentTask") or (summary.get("exploration") or {}).get("next") or {}
                    title = current.get("title") or (
                        "把刚才做过的事情讲清楚" if mode == "expression" else "继续基础练习"
                    )
                    return JSONResponse(
                        {
                            "next_action": {
                                "action": "foundation",
                                "title": title,
                                "description": "先完成眼前这一小步，不需要先选岗位。",
                                "href": "/static/foundation.html",
                                "cta": "继续做",
                            },
                            "foundation": summary,
                            "project": None,
                        }
                    )
                if path == "/api/v1/project-templates" and request.method == "GET" and not unlocked:
                    return JSONResponse(
                        {
                            "items": [],
                            "locked": True,
                            "foundation": summary,
                            "tenant_id": principal.tenant_id,
                        }
                    )
                if path == "/api/v1/projects" and request.method == "POST" and not unlocked:
                    return JSONResponse(
                        status_code=423,
                        content={
                            "detail": {
                                "code": "foundation_locked",
                                "message": "先完成基础练习，再进入职业项目。",
                                "href": "/static/foundation.html",
                                "foundation": summary,
                            }
                        },
                    )
        return await call_next(request)

    app.state.stepin_foundation_service = service
    app.state.stepin_foundation_registered = True
