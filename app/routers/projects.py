from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth_store import Principal
from ..domain.roles import canonical_role
from ..project_models import ProjectAnswersRequest, ProjectCreateRequest
from ..project_repository import ProjectRepository, ProjectVersionConflict


def build_projects_router(
    *,
    current_principal,
    project_repository: ProjectRepository,
    create_project_session: Callable[[Principal], object],
    cleanup_project_session: Callable[[str, str], None],
    allow_anonymous_demo: bool = False,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["projects"])

    def participant_identity(principal: Principal) -> tuple[str, str]:
        if not principal.authenticated:
            if allow_anonymous_demo and principal.user_id == "demo-local":
                return principal.tenant_id, principal.user_id
            raise HTTPException(status_code=401, detail="authenticated participant required")
        role = canonical_role(principal.role)
        if role != "participant":
            raise HTTPException(status_code=403, detail="participant account required")
        owner = principal.user_id
        if not owner:
            raise HTTPException(status_code=401, detail="authenticated participant required")
        return principal.tenant_id, owner

    @router.get("/project-templates")
    def list_project_templates(principal: Principal = Depends(current_principal)):
        tenant_id, _ = participant_identity(principal)
        return {"items": project_repository.list_templates(tenant_id=tenant_id), "tenant_id": tenant_id}

    @router.get("/project-templates/{template_id}")
    def get_project_template(template_id: str, principal: Principal = Depends(current_principal)):
        tenant_id, _ = participant_identity(principal)
        try:
            template = project_repository.get_template(template_id, tenant_id=tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="project template not found")
        if template.get("status") != "published":
            raise HTTPException(status_code=404, detail="project template not found")
        return template

    @router.get("/projects")
    def list_projects(
        status: str | None = Query(default=None),
        principal: Principal = Depends(current_principal),
    ):
        tenant_id, owner = participant_identity(principal)
        try:
            items = project_repository.list_projects(
                tenant_id=tenant_id, owner_user_id=owner, status=status
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"items": items, "tenant_id": tenant_id}

    @router.post("/projects", status_code=201)
    def create_project(
        req: ProjectCreateRequest,
        principal: Principal = Depends(current_principal),
    ):
        tenant_id, owner = participant_identity(principal)
        try:
            version = project_repository.get_template_version(
                req.template_version_id, tenant_id=tenant_id
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="published project template version not found")
        if version.get("status") != "published":
            raise HTTPException(status_code=409, detail="project template version is not published")
        try:
            current = project_repository.get_template(version["template_id"], tenant_id=tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="project template not found")
        if current.get("current_version_id") != req.template_version_id:
            raise HTTPException(status_code=409, detail="project template version is not current")
        state = create_project_session(principal)
        try:
            if state.tenant_id != tenant_id or state.student_user_id != owner:
                raise HTTPException(status_code=403, detail="project session ownership mismatch")
            return project_repository.create_project(
                tenant_id=tenant_id,
                owner_user_id=owner,
                template_version_id=req.template_version_id,
                session_id=state.session_id,
                name=req.name,
            )
        except ProjectVersionConflict as exc:
            cleanup_project_session(state.session_id, tenant_id)
            raise HTTPException(status_code=409, detail=str(exc))
        except ValueError as exc:
            cleanup_project_session(state.session_id, tenant_id)
            raise HTTPException(status_code=409, detail=str(exc))
        except Exception:
            cleanup_project_session(state.session_id, tenant_id)
            raise

    @router.get("/projects/{project_id}")
    def get_project(project_id: str, principal: Principal = Depends(current_principal)):
        tenant_id, owner = participant_identity(principal)
        try:
            return project_repository.get_project(
                project_id, tenant_id=tenant_id, owner_user_id=owner
            )
        except KeyError:
            # Object-level isolation deliberately avoids revealing cross-tenant/cross-owner IDs.
            raise HTTPException(status_code=404, detail="project not found")

    @router.get("/projects/{project_id}/form")
    def get_project_form(project_id: str, principal: Principal = Depends(current_principal)):
        tenant_id, owner = participant_identity(principal)
        try:
            project = project_repository.get_project(
                project_id, tenant_id=tenant_id, owner_user_id=owner
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="project not found")
        return {
            "project_id": project_id,
            "questions": project["template"].get("questions", []),
            "answers": project.get("answers", {}),
        }

    @router.put("/projects/{project_id}/answers")
    def save_project_answers(
        project_id: str,
        req: ProjectAnswersRequest,
        principal: Principal = Depends(current_principal),
    ):
        tenant_id, owner = participant_identity(principal)
        try:
            project = project_repository.get_project(
                project_id, tenant_id=tenant_id, owner_user_id=owner
            )
        except KeyError:
            raise HTTPException(status_code=404, detail="project not found")
        allowed = {str(q.get("question_id")) for q in project["template"].get("questions", [])}
        unknown = sorted({item.question_id for item in req.answers} - allowed)
        if unknown:
            raise HTTPException(status_code=422, detail={"unknown_question_ids": unknown})
        for item in req.answers:
            project_repository.save_answer(
                project_id,
                item.question_id,
                item.answer,
                tenant_id=tenant_id,
                owner_user_id=owner,
            )
        return {
            "project_id": project_id,
            "answers": project_repository.list_answers(
                project_id, tenant_id=tenant_id, owner_user_id=owner
            ),
        }

    return router
