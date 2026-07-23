from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import DataSubjectRequestCreate, PrivacyConsentRequest


def build_privacy_router(*, current_principal, require_roles, auth_store, session_store, artifact_store,
                         evidence_store, evidence_graph, collaboration_store, storage_registry,
                         data_lifecycle, settings) -> APIRouter:
    router = APIRouter(tags=["privacy"])

    @router.post("/api/privacy/consents")
    def privacy_record_consent(req: PrivacyConsentRequest, principal=Depends(current_principal)):
        if not principal.authenticated:
            raise HTTPException(status_code=403, detail="authentication required")
        return {"ok": True, "consent": auth_store.record_consent(
            tenant_id=principal.tenant_id, user_id=principal.user_id, policy_version=req.policy_version,
            purpose=req.purpose, granted=req.granted, source=req.source,
        )}

    @router.get("/api/privacy/consents")
    def privacy_list_consents(principal=Depends(current_principal)):
        if not principal.authenticated:
            raise HTTPException(status_code=403, detail="authentication required")
        return {"consents": auth_store.list_consents(tenant_id=principal.tenant_id, user_id=principal.user_id)}

    def export_bundle(principal) -> dict:
        sessions = []
        for state, updated_at in session_store.list(limit=5000, tenant_id=principal.tenant_id, student_user_id=principal.user_id):
            sid = state.session_id
            sessions.append({
                "session": state.model_dump(mode="json"),
                "updated_at": updated_at,
                "artifacts": artifact_store.list_session(sid, include_content=True, tenant_id=principal.tenant_id, all_versions=True),
                "evidence": evidence_store.list_session(sid, limit=5000, tenant_id=principal.tenant_id),
                "claims": evidence_graph.list_claims(sid, tenant_id=principal.tenant_id),
                "feedback": collaboration_store.list_feedback(sid, tenant_id=principal.tenant_id),
            })
        return {
            "export_version": "1.0-beta1",
            "identity": auth_store.get_user(principal.user_id, include_memberships=True),
            "consents": auth_store.list_consents(tenant_id=principal.tenant_id, user_id=principal.user_id),
            "sessions": sessions,
            "tasks": collaboration_store.list_tasks(principal.tenant_id, limit=5000, owner_user_id=principal.user_id),
            "files": storage_registry.list(tenant_id=principal.tenant_id, owner_user_id=principal.user_id, limit=500),
        }

    @router.get("/api/privacy/export")
    def privacy_export(principal=Depends(current_principal)):
        if not principal.authenticated:
            raise HTTPException(status_code=403, detail="authentication required")
        auth_store.audit(tenant_id=principal.tenant_id, user_id=principal.user_id, action="privacy_export",
                         resource_type="user", resource_id=principal.user_id)
        return export_bundle(principal)

    @router.post("/api/privacy/requests")
    def privacy_create_request(req: DataSubjectRequestCreate, principal=Depends(current_principal)):
        if not principal.authenticated:
            raise HTTPException(status_code=403, detail="authentication required")
        item = auth_store.create_data_subject_request(
            tenant_id=principal.tenant_id, user_id=principal.user_id, request_type=req.request_type, notes=req.notes
        )
        return {"ok": True, "request": item,
                "note": "Delete requests require controlled processing; this endpoint does not silently erase shared records."}

    @router.get("/api/privacy/requests")
    def privacy_list_requests(principal=Depends(current_principal)):
        if not principal.authenticated:
            raise HTTPException(status_code=403, detail="authentication required")
        return {"requests": auth_store.list_data_subject_requests(tenant_id=principal.tenant_id, user_id=principal.user_id)}

    @router.get("/api/admin/privacy/requests")
    def admin_privacy_requests(principal=Depends(require_roles("school_admin"))):
        return {"requests": auth_store.list_data_subject_requests(tenant_id=principal.tenant_id)}

    @router.get("/api/admin/privacy/requests/{request_id}/plan")
    def admin_privacy_request_plan(request_id: str, principal=Depends(require_roles("school_admin"))):
        try:
            item = auth_store.get_data_subject_request(request_id, principal.tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="privacy request not found")
        if item.get("request_type") != "delete":
            raise HTTPException(status_code=400, detail="only delete requests have a deletion plan")
        return {"request": item, "plan": data_lifecycle.plan_user_deletion(
            tenant_id=principal.tenant_id, user_id=item["user_id"]
        ).to_dict()}

    @router.post("/api/admin/privacy/requests/{request_id}/process")
    def admin_process_privacy_request(request_id: str, confirm: bool = Query(default=False),
                                      principal=Depends(require_roles("school_admin"))):
        try:
            item = auth_store.get_data_subject_request(request_id, principal.tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="privacy request not found")
        if item.get("request_type") != "delete":
            raise HTTPException(status_code=400, detail="unsupported request type for this processor")
        plan = data_lifecycle.plan_user_deletion(tenant_id=principal.tenant_id, user_id=item["user_id"]).to_dict()
        if not confirm:
            return {"ok": True, "executed": False, "plan": plan,
                    "note": "Set confirm=true after policy/legal review to execute."}
        if not settings.privacy_delete_executor_enabled:
            raise HTTPException(status_code=409, detail="privacy deletion executor is disabled by configuration")
        auth_store.update_data_subject_request(request_id=request_id, tenant_id=principal.tenant_id,
                                               status="processing", result={"plan": plan})
        try:
            result = data_lifecycle.execute_user_deletion(tenant_id=principal.tenant_id, user_id=item["user_id"])
            auth_store.update_data_subject_request(request_id=request_id, tenant_id=principal.tenant_id,
                                                   status="completed", result=result)
            auth_store.audit(tenant_id=principal.tenant_id, user_id=principal.user_id,
                             action="privacy_delete_processed", resource_type="data_subject_request",
                             resource_id=request_id, details={"target_user_id": item["user_id"]})
            return {"ok": True, "executed": True, "result": result}
        except Exception as exc:
            auth_store.update_data_subject_request(request_id=request_id, tenant_id=principal.tenant_id,
                                                   status="rejected", result={"error": str(exc), "plan": plan})
            raise HTTPException(status_code=500, detail=f"privacy deletion processing failed: {exc}")

    return router
