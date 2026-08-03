from __future__ import annotations

from typing import Any, Callable
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from ..domain_intelligence import DomainVersionConflict
from ..models import DomainClaimUpsert, DomainGapStatusUpdate, DomainRecomputeRequest


def build_domain_intelligence_router(
    *,
    sessions: Any,
    identity: Any,
    evidence: Any,
    artifacts: Any,
    jobs: Any,
    domain_service: Any,
    domain_store: Any,
    current_principal: Callable,
    canonical_role: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/api/domain/v1", tags=["domain-intelligence"])

    def role(principal) -> str:
        return canonical_role(principal.role)

    def target_in_tenant(subject_user_id: str, principal) -> bool:
        if subject_user_id == principal.user_id:
            return True
        try:
            return any(
                m.get("tenant_id") == principal.tenant_id and m.get("status", "active") == "active"
                for m in identity.memberships(subject_user_id)
            )
        except Exception:
            return False

    def can_access_subject(principal, subject_user_id: str) -> bool:
        if not subject_user_id or subject_user_id == principal.user_id:
            return True
        if not target_in_tenant(subject_user_id, principal):
            return False
        if principal.is_super_admin or role(principal) == "organization_admin":
            return True
        if role(principal) == "advisor":
            advisor_groups = identity.user_class_ids(principal.user_id, principal.tenant_id, role="teacher")
            student_groups = identity.user_class_ids(subject_user_id, principal.tenant_id, role="student")
            return bool(advisor_groups & student_groups)
        return False

    def subject(principal, requested: str = "") -> str:
        target = (requested or principal.user_id or "demo-local").strip()
        if not can_access_subject(principal, target):
            raise HTTPException(status_code=403, detail={"code": "subject_access_denied"})
        return target

    def session_for(principal, requested: str = "", *, create: bool = False):
        target = subject(principal, requested)
        rows = sessions.list(limit=1, tenant_id=principal.tenant_id, student_user_id=target)
        if rows:
            return rows[0][0]
        if not create:
            raise HTTPException(status_code=404, detail={"code": "workspace_not_initialized"})
        group_ids = sorted(identity.user_class_ids(target, principal.tenant_id, role="student")) if target else []
        return sessions.create(
            tenant_id=principal.tenant_id,
            student_user_id=target,
            class_id=(group_ids[0] if group_ids else "default"),
            student_id=target,
        )

    def current_inputs(state) -> tuple[list[dict], list[dict]]:
        evidence_rows = evidence.list_session(state.session_id, limit=5000, tenant_id=state.tenant_id)
        artifact_rows = artifacts.list_session(
            state.session_id,
            include_content=True,
            tenant_id=state.tenant_id,
            all_versions=False,
        )
        return evidence_rows, artifact_rows

    @router.get("/snapshot")
    def snapshot(
        subject_user_id: str = Query(default=""),
        job_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        state = session_for(principal, subject_user_id, create=False)
        data = domain_service.snapshot(tenant_id=state.tenant_id, session_id=state.session_id, job_id=job_id)
        return {
            "ok": True,
            "tenant_id": state.tenant_id,
            "session_id": state.session_id,
            "subject_user_id": state.student_user_id,
            "job_id": job_id,
            "data": data,
        }

    @router.post("/recompute")
    def recompute(
        req: DomainRecomputeRequest,
        subject_user_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        state = session_for(principal, subject_user_id, create=True)
        evidence_rows, artifact_rows = current_inputs(state)
        if req.job_id:
            try:
                jobs.get(req.job_id, tenant_id=state.tenant_id)
            except KeyError:
                raise HTTPException(status_code=404, detail={"code": "job_not_found"})
        result = domain_service.recompute(
            tenant_id=state.tenant_id,
            session_id=state.session_id,
            owner_user_id=state.student_user_id,
            actor_user_id=principal.user_id,
            job_id=req.job_id,
            evidence_items=evidence_rows,
            artifact_items=artifact_rows,
        )
        return {
            "ok": True,
            "job_id": req.job_id,
            "claims": result.claims,
            "claim_evidence_links": result.claim_evidence_links,
            "claim_capability_links": result.claim_capability_links,
            "requirement_capability_links": result.requirement_capability_links,
            "capabilities": result.assessments,
            "gaps": result.gaps,
            "explanation": result.explanation,
        }

    @router.get("/claims")
    def list_claims(subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = session_for(principal, subject_user_id, create=False)
        return {"ok": True, "items": domain_store.list_claims(tenant_id=state.tenant_id, session_id=state.session_id)}

    @router.post("/claims")
    def create_claim(
        req: DomainClaimUpsert,
        subject_user_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        state = session_for(principal, subject_user_id, create=True)
        source_id = f"MANUAL-{uuid4().hex[:16].upper()}"
        item = domain_store.upsert_claim(
            tenant_id=state.tenant_id,
            session_id=state.session_id,
            owner_user_id=state.student_user_id,
            source_type="manual",
            source_id=source_id,
            source_locator="0",
            claim_text=req.claim_text,
            claim_type=req.claim_type,
            actor_user_id=principal.user_id,
            reason=req.reason,
        )
        return {"ok": True, "item": item}

    @router.patch("/claims/{claim_id}")
    def update_claim(
        claim_id: str,
        req: DomainClaimUpsert,
        subject_user_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        state = session_for(principal, subject_user_id, create=False)
        try:
            item = domain_store.update_claim(
                tenant_id=state.tenant_id,
                session_id=state.session_id,
                owner_user_id=state.student_user_id,
                claim_id=claim_id,
                claim_text=req.claim_text,
                claim_type=req.claim_type,
                actor_user_id=principal.user_id,
                expected_version=req.expected_version,
                reason=req.reason,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "claim_not_found"})
        except DomainVersionConflict as exc:
            raise HTTPException(status_code=409, detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual})
        return {"ok": True, "item": item}

    @router.get("/claims/{claim_id}/versions")
    def claim_versions(claim_id: str, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = session_for(principal, subject_user_id, create=False)
        try:
            claim = domain_store.get_claim(claim_id, tenant_id=state.tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "claim_not_found"})
        if claim.get("session_id") != state.session_id:
            raise HTTPException(status_code=403, detail={"code": "claim_access_denied"})
        return {"ok": True, "items": domain_store.claim_versions(claim_id, tenant_id=state.tenant_id)}

    @router.get("/capabilities")
    def capabilities(subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = session_for(principal, subject_user_id, create=False)
        return {"ok": True, "items": domain_store.latest_assessments(tenant_id=state.tenant_id, session_id=state.session_id)}

    @router.get("/capabilities/{capability_id}/explain")
    def explain_capability(capability_id: str, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = session_for(principal, subject_user_id, create=False)
        try:
            data = domain_store.explain_capability(capability_id, tenant_id=state.tenant_id, session_id=state.session_id)
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "capability_not_found"})
        return {"ok": True, "data": data}

    @router.get("/capabilities/{capability_id}/versions")
    def capability_versions(capability_id: str, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = session_for(principal, subject_user_id, create=False)
        return {"ok": True, "items": domain_store.assessment_versions(capability_id, tenant_id=state.tenant_id, session_id=state.session_id)}

    @router.get("/requirements")
    def requirement_mappings(
        job_id: str = Query(min_length=1),
        subject_user_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        state = session_for(principal, subject_user_id, create=False)
        return {"ok": True, "items": domain_store.requirement_mappings(tenant_id=state.tenant_id, job_id=job_id)}

    @router.get("/requirements/{requirement_id}/versions")
    def requirement_versions(requirement_id: str, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = session_for(principal, subject_user_id, create=False)
        return {"ok": True, "items": domain_store.requirement_versions(requirement_id, tenant_id=state.tenant_id)}

    @router.get("/gaps")
    def gaps(
        job_id: str = Query(default=""),
        subject_user_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        state = session_for(principal, subject_user_id, create=False)
        return {"ok": True, "items": domain_store.list_gaps(tenant_id=state.tenant_id, session_id=state.session_id, job_id=job_id)}

    @router.patch("/gaps/{gap_id}")
    def update_gap(
        gap_id: str,
        req: DomainGapStatusUpdate,
        subject_user_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        state = session_for(principal, subject_user_id, create=False)
        try:
            item = domain_store.update_gap_status(
                tenant_id=state.tenant_id,
                session_id=state.session_id,
                owner_user_id=state.student_user_id,
                gap_id=gap_id,
                status=req.status,
                actor_user_id=principal.user_id,
                expected_version=req.expected_version,
                reason=req.reason,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "gap_not_found"})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "invalid_gap_status", "message": str(exc)})
        except DomainVersionConflict as exc:
            raise HTTPException(status_code=409, detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual})
        return {"ok": True, "item": item}

    @router.get("/gaps/{gap_id}/versions")
    def gap_versions(gap_id: str, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = session_for(principal, subject_user_id, create=False)
        items = domain_store.gap_versions(gap_id, tenant_id=state.tenant_id)
        if items and items[0].get("snapshot", {}).get("session_id") != state.session_id:
            raise HTTPException(status_code=403, detail={"code": "gap_access_denied"})
        return {"ok": True, "items": items}

    @router.get("/audit")
    def audit(
        subject_user_id: str = Query(default=""),
        entity_type: str = Query(default=""),
        entity_id: str = Query(default=""),
        limit: int = Query(default=200, ge=1, le=1000),
        principal=Depends(current_principal),
    ):
        state = session_for(principal, subject_user_id, create=False)
        return {
            "ok": True,
            "items": domain_store.audit_events(
                tenant_id=state.tenant_id,
                session_id=state.session_id,
                entity_type=entity_type,
                entity_id=entity_id,
                limit=limit,
            ),
        }

    return router
