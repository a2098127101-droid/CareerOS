from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import (
    ArtifactTemplateCreateRequest,
    ArtifactTemplateUpdateRequest,
    WorkflowTemplateCreateRequest,
    WorkflowTemplateUpdateRequest,
)


def build_template_admin_router(*, template_registry, admin_dependency):
    router = APIRouter(tags=["template-admin"])

    @router.get("/api/admin/templates/workflows")
    def list_workflows(preset_id: str = Query(default=""), principal=Depends(admin_dependency)):
        return {"templates": template_registry.list_workflows(tenant_id=principal.tenant_id, preset_id=preset_id)}

    @router.post("/api/admin/templates/workflows")
    def create_workflow(req: WorkflowTemplateCreateRequest, principal=Depends(admin_dependency)):
        try:
            item = template_registry.create_workflow(
                tenant_id=principal.tenant_id, preset_id=req.preset_id, name=req.name,
                steps=req.steps, created_by=principal.user_id,
            )
            return {"ok": True, "template": item}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.put("/api/admin/templates/workflows/{template_id}")
    def update_workflow(template_id: str, req: WorkflowTemplateUpdateRequest, principal=Depends(admin_dependency)):
        try:
            item = template_registry.update_workflow(
                template_id, tenant_id=principal.tenant_id, name=req.name, steps=req.steps,
            )
            return {"ok": True, "template": item}
        except KeyError:
            raise HTTPException(status_code=404, detail="workflow template not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/api/admin/templates/workflows/{template_id}/activate")
    def activate_workflow(template_id: str, principal=Depends(admin_dependency)):
        try:
            return {"ok": True, "template": template_registry.activate_workflow(template_id, tenant_id=principal.tenant_id)}
        except KeyError:
            raise HTTPException(status_code=404, detail="workflow template not found")

    @router.get("/api/admin/templates/artifacts")
    def list_artifacts(preset_id: str = Query(default=""), principal=Depends(admin_dependency)):
        return {"templates": template_registry.list_artifacts(tenant_id=principal.tenant_id, preset_id=preset_id)}

    @router.post("/api/admin/templates/artifacts")
    def create_artifact(req: ArtifactTemplateCreateRequest, principal=Depends(admin_dependency)):
        try:
            item = template_registry.create_artifact(
                tenant_id=principal.tenant_id, kind=req.kind, label=req.label, aliases=req.aliases,
                renderer=req.renderer, review_rubric=req.review_rubric, presets=req.presets,
                schema=req.schema_definition, created_by=principal.user_id,
            )
            return {"ok": True, "template": item}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.put("/api/admin/templates/artifacts/{template_id}")
    def update_artifact(template_id: str, req: ArtifactTemplateUpdateRequest, principal=Depends(admin_dependency)):
        try:
            item = template_registry.update_artifact(
                template_id, tenant_id=principal.tenant_id, label=req.label, aliases=req.aliases,
                renderer=req.renderer, review_rubric=req.review_rubric, presets=req.presets,
                schema=req.schema_definition,
            )
            return {"ok": True, "template": item}
        except KeyError:
            raise HTTPException(status_code=404, detail="artifact template not found")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @router.post("/api/admin/templates/artifacts/{template_id}/activate")
    def activate_artifact(template_id: str, principal=Depends(admin_dependency)):
        try:
            return {"ok": True, "template": template_registry.activate_artifact(template_id, tenant_id=principal.tenant_id)}
        except KeyError:
            raise HTTPException(status_code=404, detail="artifact template not found")

    return router
