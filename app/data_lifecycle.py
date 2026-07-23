from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class DeletionPlan:
    tenant_id: str
    user_id: str
    session_ids: list[str]
    artifacts: int
    evidence_items: int
    claims: int
    feedback: int
    tasks: int
    files: int
    retained_categories: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DataLifecycleService:
    """Controlled privacy deletion/de-identification orchestration.

    User-owned operational data is deleted. Audit/security/billing records are retained as
    pseudonymous records because they may be required for fraud, accounting, or legal retention.
    This service deliberately does not claim universal hard deletion of every historical row.
    """

    def __init__(self, *, sessions, artifacts, evidence, evidence_graph, workflows, collaboration, identity, storage_registry, object_storage):
        self.sessions = sessions
        self.artifacts = artifacts
        self.evidence = evidence
        self.evidence_graph = evidence_graph
        self.workflows = workflows
        self.collaboration = collaboration
        self.identity = identity
        self.storage_registry = storage_registry
        self.object_storage = object_storage

    def plan_user_deletion(self, *, tenant_id: str, user_id: str) -> DeletionPlan:
        owned_sessions = self.sessions.list(limit=10000, tenant_id=tenant_id, student_user_id=user_id)
        session_ids = [state.session_id for state, _ in owned_sessions]
        artifacts = evidence_items = claims = feedback = tasks = 0
        for sid in session_ids:
            artifacts += len(self.artifacts.list_session(sid, include_content=False, tenant_id=tenant_id, all_versions=True))
            evidence_items += len(self.evidence.list_session(sid, limit=10000, tenant_id=tenant_id))
            try:
                claims += len(self.evidence_graph.list_claims(sid, tenant_id=tenant_id))
            except Exception:
                pass
            feedback += len(self.collaboration.list_feedback(sid, tenant_id=tenant_id))
            tasks += len(self.collaboration.list_tasks(tenant_id=tenant_id, session_id=sid, limit=10000))
        files = self.storage_registry.count(tenant_id=tenant_id, owner_user_id=user_id)
        return DeletionPlan(
            tenant_id=tenant_id,
            user_id=user_id,
            session_ids=session_ids,
            artifacts=artifacts,
            evidence_items=evidence_items,
            claims=claims,
            feedback=feedback,
            tasks=tasks,
            files=files,
            retained_categories=["security_audit_log", "billing_events", "billing_orders", "aggregated_or_pseudonymous_analytics"],
        )

    def execute_user_deletion(self, *, tenant_id: str, user_id: str) -> dict[str, Any]:
        plan = self.plan_user_deletion(tenant_id=tenant_id, user_id=user_id)
        deleted = {
            "sessions": 0,
            "artifact_versions": 0,
            "evidence_items": 0,
            "claims": 0,
            "reviews": 0,
            "graph_edges": 0,
            "feedback": 0,
            "tasks": 0,
            "workflow_instances": 0,
            "workflow_steps": 0,
            "files": 0,
        }
        # Files first so private objects are removed while ownership metadata is still available.
        while True:
            batch = self.storage_registry.list(tenant_id=tenant_id, owner_user_id=user_id, limit=500)
            if not batch:
                break
            for meta in batch:
                try:
                    self.object_storage.delete(meta["object_key"])
                finally:
                    if self.storage_registry.mark_deleted(meta["object_id"], tenant_id=tenant_id):
                        deleted["files"] += 1

        for sid in plan.session_ids:
            graph = self.evidence_graph.delete_session(sid, tenant_id=tenant_id)
            deleted["claims"] += int(graph.get("claims", 0))
            deleted["reviews"] += int(graph.get("reviews", 0))
            deleted["graph_edges"] += int(graph.get("edges", 0))
            deleted["artifact_versions"] += int(self.artifacts.delete_session(sid, tenant_id=tenant_id))
            deleted["evidence_items"] += int(self.evidence.delete_session(sid, tenant_id=tenant_id))
            collab = self.collaboration.delete_session(sid, tenant_id=tenant_id)
            deleted["feedback"] += int(collab.get("feedback", 0))
            deleted["tasks"] += int(collab.get("tasks", 0))
            wf = self.workflows.delete_session(sid, tenant_id=tenant_id)
            deleted["workflow_instances"] += int(wf.get("instances", 0))
            deleted["workflow_steps"] += int(wf.get("steps", 0))
            if self.sessions.delete_session(sid, tenant_id=tenant_id):
                deleted["sessions"] += 1

        identity = self.identity.anonymize_user_identity(user_id=user_id, tenant_id=tenant_id)
        return {
            "mode": "delete_user_owned_and_deidentify_identity",
            "plan": plan.to_dict(),
            "deleted": deleted,
            "identity": identity,
            "retained_categories": plan.retained_categories,
            "note": "Security/audit/billing and other legally retained records are not hard-deleted by this executor; identity is pseudonymized instead.",
        }
