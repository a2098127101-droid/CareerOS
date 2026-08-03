from __future__ import annotations

from secrets import token_urlsafe
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import (
    WorkspaceArtifactUpsert,
    WorkspaceEvidenceUpsert,
    WorkspaceTaskUpsert,
    WorkspaceUserCreate,
    WorkspaceCoachRequest,
    WorkspaceInterviewEvaluateRequest,
    WorkspacePPTReviewRequest,
    WorkspaceInterviewEvaluation,
    WorkspacePPTReviewResult,
    WorkspaceEvidenceVerificationDecision,
)
from ..unified_runtime_store import RuntimeVersionConflict
from ..role_policy import RolePolicy


def build_workspace_router(
    *,
    sessions: Any,
    identity: Any,
    evidence: Any,
    evidence_graph: Any,
    artifacts: Any,
    collaboration: Any,
    knowledge: Any,
    jobs: Any,
    agents: Any,
    current_principal: Callable,
    canonical_role: Callable,
) -> APIRouter:
    """Canonical-domain BFF for the unified H5.

    This router intentionally maps UI-friendly payloads to the existing canonical stores instead of
    persisting duplicate Evidence/Artifact/User/Task/Knowledge/Job JSON in the generic runtime table.
    """
    router = APIRouter(prefix="/api/workspace/v1", tags=["workspace-canonical"])
    role_policy = RolePolicy()

    def role(principal) -> str:
        return canonical_role(principal.role)

    def is_staff(principal) -> bool:
        return bool(principal.is_super_admin or role(principal) in {"organization_admin", "advisor"})

    def target_in_tenant(subject_user_id: str, principal) -> bool:
        if subject_user_id == principal.user_id:
            return True
        try:
            return any(m.get("tenant_id") == principal.tenant_id and m.get("status", "active") == "active" for m in identity.memberships(subject_user_id))
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
            raise HTTPException(status_code=403, detail="subject user access denied")
        return target

    def ensure_session(principal, subject_user_id: str = ""):
        target = subject(principal, subject_user_id)
        rows = sessions.list(limit=1, tenant_id=principal.tenant_id, student_user_id=target)
        if rows:
            return rows[0][0]
        # A canonical workspace session can be created by the participant or an authorized staff
        # member. The subject remains the owner; staff never becomes the data owner.
        group_ids = sorted(identity.user_class_ids(target, principal.tenant_id, role="student")) if target else []
        return sessions.create(
            tenant_id=principal.tenant_id,
            student_user_id=target,
            class_id=(group_ids[0] if group_ids else "default"),
            student_id=target,
        )

    def workspace_evidence(row: dict) -> dict:
        fn = getattr(evidence, "to_workspace_item", None)
        if fn:
            return fn(row)
        return {
            "id": row.get("evidence_id", ""), "title": row.get("source_label", "Evidence"),
            "action": row.get("content", ""), "proof": "", "capabilities": [],
            "verified": bool(row.get("verified")), "createdAt": str(row.get("created_at") or ""),
            "updatedAt": str(row.get("updated_at") or row.get("created_at") or ""),
            "_version": int(row.get("version") or 1),
        }

    def workspace_artifact(row: dict) -> dict:
        fn = getattr(artifacts, "to_workspace_item", None)
        if fn:
            return fn(row)
        return {"id": row.get("artifact_id", ""), "title": row.get("title", "Artifact"), "type": row.get("kind", "custom"),
                "content": row.get("content", ""), "evidenceIds": [], "_version": int(row.get("version") or 1)}

    def workspace_task(row: dict) -> dict:
        payload = row.get("payload") or {}
        status = row.get("status") or "todo"
        return {
            "id": row.get("task_id", ""), "title": row.get("title", "Task"),
            "description": payload.get("description", ""), "type": row.get("task_type", "custom"),
            "priority": "High" if row.get("priority") == "high" else "Normal",
            "status": "done" if status in {"done", "completed"} else ("cancelled" if status == "cancelled" else "todo"),
            "owner": row.get("owner_user_id", "") or "Self", "originType": payload.get("originType", row.get("source", "manual")),
            "originId": payload.get("originId", ""), "createdAt": str(row.get("created_at") or ""),
            "updatedAt": str(row.get("updated_at") or ""), "_version": int(row.get("version") or 1),
        }

    @router.get("/context")
    def context(subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        return {"ok": True, "session_id": state.session_id, "tenant_id": state.tenant_id,
                "subject_user_id": state.student_user_id, "profile": state.profile.model_dump(), "stage": state.stage}

    @router.get("/bootstrap")
    def bootstrap(subject_user_id: str = Query(default=""), job_limit: int = Query(default=100, ge=1, le=500), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        ev = [workspace_evidence(x) for x in evidence.list_session(state.session_id, limit=1000, tenant_id=state.tenant_id)]
        arts = [workspace_artifact(x) for x in artifacts.list_session(state.session_id, include_content=True, tenant_id=state.tenant_id, all_versions=False)]
        tasks = [workspace_task(x) for x in collaboration.list_tasks(tenant_id=state.tenant_id, session_id=state.session_id, limit=1000)]
        users = identity.list_users(state.tenant_id) if is_staff(principal) else []
        sources = knowledge.list_sources(state.tenant_id) if is_staff(principal) else []
        job_rows = jobs.search("", limit=job_limit, tenant_id=state.tenant_id) if is_staff(principal) else []
        return {
            "ok": True, "session": state.model_dump(), "subject_user_id": state.student_user_id,
            "evidence": ev, "artifacts": arts, "tasks": tasks, "users": users,
            "knowledge": sources, "jobs": job_rows,
            "evidence_graph": evidence_graph.session_graph(state.session_id, tenant_id=state.tenant_id),
        }

    @router.get("/modules")
    def modules(subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        """Return the server-authoritative workspace capability contract.

        The frontend uses this endpoint to explain role and data availability instead of
        presenting navigation items as unconditional static links.
        """
        state = ensure_session(principal, subject_user_id)
        evidence_items = evidence.list_session(state.session_id, limit=1000, tenant_id=state.tenant_id)
        artifact_items = artifacts.list_session(
            state.session_id, include_content=False, tenant_id=state.tenant_id, all_versions=False
        )
        task_items = collaboration.list_tasks(
            tenant_id=state.tenant_id, session_id=state.session_id, limit=1000
        )
        staff = is_staff(principal)
        return {
            "ok": True,
            "role": role(principal),
            "tenant_id": state.tenant_id,
            "session_id": state.session_id,
            "modules": [
                {"id": "coach", "enabled": True, "write": True},
                {"id": "exploration", "enabled": True, "write": True, "count": len(evidence_items)},
                {"id": "positioning", "enabled": True, "write": True},
                {"id": "capabilities", "enabled": True, "write": True},
                {"id": "tasks", "enabled": True, "write": True, "count": len(task_items)},
                {"id": "artifacts", "enabled": True, "write": True, "count": len(artifact_items)},
                {"id": "review", "enabled": True, "write": True},
                {"id": "interview", "enabled": True, "write": True},
                {"id": "users", "enabled": staff, "write": staff},
                {"id": "knowledge", "enabled": staff, "write": bool(principal.is_super_admin or role(principal) == "organization_admin")},
                {"id": "models", "enabled": staff, "write": bool(principal.is_super_admin or role(principal) == "organization_admin")},
            ],
        }

    # -------- Evidence: canonical EvidenceStore + EvidenceGraph --------
    @router.get("/evidence")
    def list_evidence(subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        return {"ok": True, "items": [workspace_evidence(x) for x in evidence.list_session(state.session_id, limit=1000, tenant_id=state.tenant_id)]}

    @router.post("/evidence")
    def create_evidence(req: WorkspaceEvidenceUpsert, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        if req.verified:
            raise HTTPException(status_code=403, detail={"code": "self_verification_forbidden"})
        item = evidence.add_structured(
            state.session_id, title=req.title, action=req.action, proof=req.proof, capabilities=req.capabilities,
            verified=False, tenant_id=state.tenant_id, owner_user_id=state.student_user_id, evidence_id=(req.id or None),
        )
        return {"ok": True, "item": workspace_evidence(item), "graph": evidence_graph.session_graph(state.session_id, tenant_id=state.tenant_id)}

    @router.patch("/evidence/{evidence_id}")
    def update_evidence(evidence_id: str, req: WorkspaceEvidenceUpsert, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        if req.verified:
            raise HTTPException(status_code=403, detail={"code": "self_verification_forbidden"})
        try:
            item = evidence.update_structured(
                evidence_id, tenant_id=state.tenant_id, owner_user_id=state.student_user_id,
                title=req.title, action=req.action, proof=req.proof, capabilities=req.capabilities,
                verified=None, expected_version=req.expected_version,
            )
        except RuntimeVersionConflict as exc:
            raise HTTPException(status_code=409, detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual})
        except KeyError:
            raise HTTPException(status_code=404, detail="evidence not found")
        return {"ok": True, "item": workspace_evidence(item)}

    @router.post("/evidence/{evidence_id}/verification")
    def verify_evidence(
        evidence_id: str, req: WorkspaceEvidenceVerificationDecision, subject_user_id: str = Query(default=""),
        principal=Depends(current_principal),
    ):
        state = ensure_session(principal, subject_user_id)
        actor_role = role(principal)
        if req.decision != "submit_review" and actor_role not in {"advisor", "organization_admin", "platform_admin"} and not principal.is_super_admin:
            raise HTTPException(status_code=403, detail={"code": "evidence_review_role_required"})
        if req.decision != "submit_review" and actor_role == "advisor" and not can_access_subject(principal, state.student_user_id):
            raise HTTPException(status_code=403, detail={"code": "subject_access_denied"})
        try:
            item = evidence.verify_item(
                evidence_id, tenant_id=state.tenant_id, owner_user_id=state.student_user_id,
                decision=req.decision, actor_user_id=principal.user_id, reason=req.reason,
                confidence=req.confidence, method=req.method,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "evidence_not_found"})
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"code": "invalid_verification_decision", "message": str(exc)})
        return {"ok": True, "item": workspace_evidence(item), "history": evidence.verification_history(evidence_id, tenant_id=state.tenant_id)}

    @router.get("/evidence/{evidence_id}/verification-history")
    def evidence_verification_history(evidence_id: str, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        try:
            item = evidence.get(evidence_id, tenant_id=state.tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail={"code": "evidence_not_found"})
        if item.get("session_id") != state.session_id:
            raise HTTPException(status_code=403, detail={"code": "evidence_access_denied"})
        return {"ok": True, "items": evidence.verification_history(evidence_id, tenant_id=state.tenant_id)}

    @router.delete("/evidence/{evidence_id}")
    def delete_evidence(evidence_id: str, subject_user_id: str = Query(default=""), expected_version: int | None = Query(default=None), force: bool = Query(default=False), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        refs = []
        for artifact in artifacts.list_session(state.session_id, include_content=True, tenant_id=state.tenant_id, all_versions=False):
            item = workspace_artifact(artifact)
            if evidence_id in (item.get("evidenceIds") or []):
                refs.append({"artifact_id": item.get("id"), "title": item.get("title")})
        if refs and not force:
            raise HTTPException(status_code=409, detail={"code": "evidence_in_use", "dependencies": refs})
        try:
            deleted = evidence.delete_item(evidence_id, tenant_id=state.tenant_id, owner_user_id=state.student_user_id, expected_version=expected_version)
        except RuntimeVersionConflict as exc:
            raise HTTPException(status_code=409, detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual})
        return {"ok": True, "deleted": deleted, "dependencies": refs}

    # -------- Artifact: canonical immutable version chain --------
    @router.get("/artifacts")
    def list_artifacts(subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        return {"ok": True, "items": [workspace_artifact(x) for x in artifacts.list_session(state.session_id, include_content=True, tenant_id=state.tenant_id, all_versions=False)]}

    @router.post("/artifacts")
    def create_artifact(req: WorkspaceArtifactUpsert, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        item = artifacts.create_workspace_version(
            session_id=state.session_id, title=req.title, kind=req.type, content=req.content,
            evidence_ids=req.evidence_ids, tenant_id=state.tenant_id, owner_user_id=state.student_user_id,
            created_by=principal.user_id or "demo-local", artifact_id=(req.id or None),
        )
        trace = evidence_graph.trace_artifact_version(
            tenant_id=state.tenant_id, session_id=state.session_id, artifact_id=item["artifact_id"],
            version_id=item["version_id"], content=req.content,
            evidence_items=evidence.list_session(state.session_id, limit=1000, tenant_id=state.tenant_id),
        )
        return {"ok": True, "item": workspace_artifact(item), "trace": trace}

    @router.patch("/artifacts/{artifact_id}")
    def update_artifact(artifact_id: str, req: WorkspaceArtifactUpsert, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        previous = artifacts.get(artifact_id, tenant_id=state.tenant_id)
        try:
            item = artifacts.update_workspace_artifact(
                artifact_id, tenant_id=state.tenant_id, owner_user_id=state.student_user_id,
                title=req.title, content=req.content, kind=req.type, evidence_ids=req.evidence_ids,
                created_by=principal.user_id or "demo-local", expected_version=req.expected_version,
            )
        except RuntimeVersionConflict as exc:
            raise HTTPException(status_code=409, detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual})
        except (KeyError, PermissionError):
            raise HTTPException(status_code=404, detail="artifact not found")
        trace = evidence_graph.trace_artifact_version(
            tenant_id=state.tenant_id, session_id=state.session_id, artifact_id=item["artifact_id"],
            version_id=item["version_id"], content=req.content,
            evidence_items=evidence.list_session(state.session_id, limit=1000, tenant_id=state.tenant_id),
        )
        if previous.get("version_id") and item.get("version_id") != previous.get("version_id"):
            evidence_graph.link_revision(
                tenant_id=state.tenant_id, session_id=state.session_id,
                previous_version_id=previous.get("version_id", ""), new_version_id=item.get("version_id", ""),
            )
        return {"ok": True, "item": workspace_artifact(item), "trace": trace}

    @router.delete("/artifacts/{artifact_id}")
    def delete_artifact(artifact_id: str, subject_user_id: str = Query(default=""), expected_version: int | None = Query(default=None), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        try:
            deleted = artifacts.delete_artifact(
                artifact_id, tenant_id=state.tenant_id, owner_user_id=state.student_user_id, expected_version=expected_version,
            )
        except RuntimeVersionConflict as exc:
            raise HTTPException(status_code=409, detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual})
        except PermissionError:
            raise HTTPException(status_code=403, detail="artifact access denied")
        return {"ok": True, "deleted": deleted}

    @router.get("/artifacts/{artifact_id}/versions")
    def artifact_versions(artifact_id: str, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        try:
            current = artifacts.get(artifact_id, tenant_id=state.tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="artifact not found")
        if state.student_user_id and current.get("owner_user_id") not in {"", state.student_user_id}:
            raise HTTPException(status_code=403, detail="artifact access denied")
        return {"ok": True, "versions": artifacts.list_versions(artifact_id, tenant_id=state.tenant_id)}

    # -------- Tasks: canonical collaboration task store --------
    @router.get("/tasks")
    def list_tasks(subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        return {"ok": True, "items": [workspace_task(x) for x in collaboration.list_tasks(tenant_id=state.tenant_id, session_id=state.session_id, limit=1000)]}

    @router.post("/tasks")
    def create_task(req: WorkspaceTaskUpsert, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        priority = "high" if str(req.priority).lower() == "high" else "normal"
        item = collaboration.create_task(
            req.title, req.type, session_id=state.session_id, tenant_id=state.tenant_id, priority=priority,
            source=req.origin_type or "manual", payload={"description": req.description, "originType": req.origin_type, "originId": req.origin_id},
            owner_user_id=state.student_user_id, task_id=(req.id or None),
        )
        if req.status in {"done", "completed", "cancelled"}:
            item = collaboration.update_task(item["task_id"], status=("done" if req.status in {"done", "completed"} else "cancelled"), tenant_id=state.tenant_id)
        return {"ok": True, "item": workspace_task(item)}

    @router.patch("/tasks/{task_id}")
    def update_task(task_id: str, req: WorkspaceTaskUpsert, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        try:
            current = collaboration.get_task(task_id, tenant_id=state.tenant_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="task not found")
        if current.get("session_id") != state.session_id:
            raise HTTPException(status_code=403, detail="task access denied")
        status = "done" if req.status in {"done", "completed"} else ("cancelled" if req.status == "cancelled" else "todo")
        try:
            item = collaboration.update_task(
                task_id, status=status, priority=("high" if str(req.priority).lower() == "high" else "normal"),
                tenant_id=state.tenant_id, expected_version=req.expected_version, title=req.title, task_type=req.type,
                source=req.origin_type or "manual", payload={"description": req.description, "originType": req.origin_type, "originId": req.origin_id},
            )
        except RuntimeVersionConflict as exc:
            raise HTTPException(status_code=409, detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual})
        return {"ok": True, "item": workspace_task(item)}

    @router.delete("/tasks/{task_id}")
    def delete_task(
        task_id: str,
        subject_user_id: str = Query(default=""),
        expected_version: int | None = Query(default=None, ge=1),
        principal=Depends(current_principal),
    ):
        state = ensure_session(principal, subject_user_id)
        try:
            current = collaboration.get_task(task_id, tenant_id=state.tenant_id)
        except KeyError:
            return {"ok": True, "deleted": False}
        if current.get("session_id") != state.session_id:
            raise HTTPException(status_code=403, detail="task access denied")
        try:
            item = collaboration.update_task(
                task_id, status="cancelled", tenant_id=state.tenant_id, expected_version=expected_version
            )
        except RuntimeVersionConflict as exc:
            raise HTTPException(status_code=409, detail={"code": "version_conflict", "expected": exc.expected, "actual": exc.actual})
        return {"ok": True, "deleted": True, "soft": True, "item": workspace_task(item)}

    # -------- Identity: real tenant users/invitations, never JSON pseudo-users --------
    @router.get("/users")
    def list_users(principal=Depends(current_principal)):
        if not is_staff(principal):
            raise HTTPException(status_code=403, detail="staff role required")
        if role(principal) == "advisor" and not principal.is_super_admin:
            advisor_classes = identity.user_class_ids(principal.user_id, principal.tenant_id, role="teacher")
            items = []
            for user in identity.list_users(principal.tenant_id):
                user_id = str(user.get("user_id") or "")
                if not user_id:
                    continue
                participant_classes = identity.user_class_ids(user_id, principal.tenant_id, role="student")
                if advisor_classes & participant_classes:
                    items.append(user)
            return {"ok": True, "items": items}
        return {"ok": True, "items": identity.list_users(principal.tenant_id)}

    @router.post("/users")
    def create_user(req: WorkspaceUserCreate, principal=Depends(current_principal)):
        if not is_staff(principal):
            raise HTTPException(status_code=403, detail="staff role required")
        decision = role_policy.can_create_role(role(principal), req.role, is_super_admin=principal.is_super_admin)
        if not decision.allowed:
            raise HTTPException(status_code=403, detail={"code": "role_escalation_forbidden", "message": decision.reason})
        if req.invite_only or not req.password:
            invitation = identity.create_invitation(
                email=req.email, tenant_id=principal.tenant_id, role=req.role, invited_by=principal.user_id,
                display_name=req.display_name, ttl_hours=72,
            )
            return {"ok": True, "invitation": invitation, "mode": "invitation"}
        try:
            user = identity.create_user(
                email=req.email, password=req.password or token_urlsafe(24), display_name=req.display_name,
                tenant_id=principal.tenant_id, role=req.role,
            )
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, "user": user, "mode": "created"}

    @router.delete("/users/{user_id}")
    def suspend_user(user_id: str, principal=Depends(current_principal)):
        if not is_staff(principal):
            raise HTTPException(status_code=403, detail="staff role required")
        try:
            target = identity.get_user(user_id, include_memberships=True)
            membership = next((m for m in target.get("memberships", []) if m.get("tenant_id") == principal.tenant_id and m.get("status", "active") == "active"), None)
            if not membership:
                raise KeyError(user_id)
            decision = role_policy.can_disable(role(principal), membership.get("role", "participant"), is_super_admin=principal.is_super_admin, self_target=(user_id == principal.user_id))
            if not decision.allowed:
                raise HTTPException(status_code=403, detail={"code": "disable_forbidden", "message": decision.reason})
            if role(principal) == "advisor" and not can_access_subject(principal, user_id):
                raise HTTPException(status_code=403, detail={"code": "subject_access_denied"})
            user = identity.set_user_status(user_id=user_id, tenant_id=principal.tenant_id, status="disabled")
        except KeyError:
            raise HTTPException(status_code=404, detail="user not found")
        return {"ok": True, "user": user, "soft": True}


    # -------- AI feature gateway: API mode always uses the configured model gateway --------
    @router.post("/ai/coach")
    async def coach(req: WorkspaceCoachRequest, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        evidence_rows = evidence.list_session(state.session_id, limit=50, tenant_id=state.tenant_id)
        artifact_rows = artifacts.list_session(state.session_id, tenant_id=state.tenant_id, all_versions=False)[:20]
        evidence_context = [
            {"id": x.get("evidence_id"), "content": x.get("content", ""), "verified": bool(x.get("verified"))}
            for x in evidence_rows[:20]
        ]
        artifact_context = [
            {"id": x.get("artifact_id"), "title": x.get("title", ""), "kind": x.get("kind", "")}
            for x in artifact_rows[:10]
        ]
        prompt = f"""
Participant target opportunity: {state.profile.target_job or 'not specified'}
Mode: {req.mode}
Verified/current evidence JSON: {evidence_context}
Artifact inventory JSON: {artifact_context}
User message: {req.message}

Respond as a career-development coach. Ground claims in supplied evidence. Clearly label gaps or assumptions instead of inventing experience, metrics, credentials, or outcomes.
"""
        try:
            meta = await agents.gateway.complete(
                "coach",
                "You are CareerOS Coach. Be precise, evidence-grounded, actionable, and never fabricate user facts.",
                prompt,
                tenant_id=state.tenant_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail={"code": "ai_route_unavailable", "message": str(exc)})
        return {
            "ok": True, "mode": "model_gateway", "reply": meta.text,
            "provider_id": meta.provider_id, "model": meta.model, "latency_ms": meta.latency_ms,
            "usage": {"input_tokens": meta.input_tokens, "output_tokens": meta.output_tokens, "total_tokens": meta.total_tokens},
        }

    # -------- AI feature gateway: never silently falls back to fabricated scoring in API mode --------
    @router.post("/ai/interview/evaluate")
    async def evaluate_interview(req: WorkspaceInterviewEvaluateRequest, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        prompt = f"""
Target job: {req.target_job or state.profile.target_job or 'not specified'}
Interview question: {req.question}
Candidate answer: {req.answer}

Evaluate only the supplied answer. Return evidence-grounded scores. Do not invent experiences.
JSON fields: overall_score, structure, relevance, evidence, specificity, role_fit, feedback, risks.
"""
        try:
            report, meta = await agents.gateway.complete_json(
                "reviewer", "You are a strict career interview evaluator. Score 0-100 and explain concrete weaknesses.",
                prompt, WorkspaceInterviewEvaluation, tenant_id=state.tenant_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail={"code": "ai_route_unavailable", "message": str(exc)})
        return {"ok": True, "mode": "model_gateway", "evaluation": report.model_dump(),
                "provider_id": meta.provider_id, "model": meta.model, "latency_ms": meta.latency_ms, "usage": {"total_tokens": meta.total_tokens}}

    @router.post("/ai/ppt/review")
    async def review_ppt(req: WorkspacePPTReviewRequest, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        state = ensure_session(principal, subject_user_id)
        prompt = f"""
Target job: {req.target_job or state.profile.target_job or 'not specified'}
Slides JSON: {req.slides}

Review narrative, evidence grounding, logic, role fit and density. Every issue must identify a slide and a concrete correction.
JSON fields: overall_score, narrative, evidence, logic, role_fit, density, issues, summary.
"""
        try:
            report, meta = await agents.gateway.complete_json(
                "reviewer", "You are a strict presentation reviewer for career-development artifacts. Never fabricate evidence.",
                prompt, WorkspacePPTReviewResult, tenant_id=state.tenant_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail={"code": "ai_route_unavailable", "message": str(exc)})
        return {"ok": True, "mode": "model_gateway", "review": report.model_dump(),
                "provider_id": meta.provider_id, "model": meta.model, "latency_ms": meta.latency_ms, "usage": {"total_tokens": meta.total_tokens}}

    return router
