from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .capability_verification import CapabilityVerificationService


SCENE_STATE_VERSION = "1.0"


class SceneStateService:
    """Aggregate server-authoritative practice state for spatial clients.

    SceneState is deliberately a read model. It contains no mutation methods and no
    capability promotion rules. React/3D clients can focus, filter, inspect and animate
    these objects, but capability/evidence authority remains in domain services.
    """

    def __init__(
        self,
        *,
        foundation: Any,
        learner_agent: Any,
        projects: Any,
        evidence: Any,
        artifacts: Any,
        capability_verification: CapabilityVerificationService,
        work_samples: Any,
    ):
        self.foundation = foundation
        self.learner_agent = learner_agent
        self.projects = projects
        self.evidence = evidence
        self.artifacts = artifacts
        self.capability_verification = capability_verification
        self.work_samples = work_samples

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _evidence_public(row: dict[str, Any]) -> dict[str, Any]:
        try:
            item = row if "verificationStatus" in row else row.copy()
            if "verificationStatus" not in item:
                status = str(item.get("verification_status") or ("VERIFIED" if item.get("verified") else "SELF_REPORTED"))
                item = {
                    "id": str(item.get("evidence_id") or ""),
                    "title": str(item.get("source_label") or "Evidence"),
                    "action": str(item.get("content") or "")[:2400],
                    "verified": status == "VERIFIED",
                    "verificationStatus": status,
                    "verificationConfidence": float(item.get("verification_confidence") or 0),
                    "createdAt": str(item.get("created_at") or ""),
                    "updatedAt": str(item.get("updated_at") or item.get("created_at") or ""),
                }
            return item
        except Exception:
            return {"id": "", "title": "Evidence", "verified": False, "verificationStatus": "UNKNOWN"}

    @staticmethod
    def _artifact_public(row: dict[str, Any]) -> dict[str, Any]:
        metadata = row.get("metadata") or {}
        evidence_ids = list(metadata.get("workspace_evidence_ids") or [])
        if not evidence_ids:
            evidence_ids = [x.get("evidence_id") for x in (row.get("evidence_links") or []) if x.get("evidence_id")]
        return {
            "id": str(row.get("artifact_id") or ""),
            "versionId": str(row.get("version_id") or ""),
            "version": int(row.get("version") or 1),
            "title": str(row.get("title") or "Artifact"),
            "kind": str(row.get("kind") or "custom"),
            "evidenceIds": evidence_ids,
            "isCurrent": bool(row.get("is_current")),
            "createdAt": str(row.get("created_at") or ""),
        }

    @staticmethod
    def _node(node_id: str, kind: str, label: str, *, zone: str, state: str = "available", ref_id: str = "", data: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "id": node_id,
            "kind": kind,
            "label": label,
            "zone": zone,
            "state": state,
            "refId": ref_id,
            "data": data or {},
            "authority": "server",
            "readOnly": True,
        }

    def build(
        self,
        *,
        tenant_id: str,
        owner_user_id: str,
        session_id: str,
        identity: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        foundation = self.foundation.summary(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
        )
        agent_state = self.learner_agent.get_state(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
        ).model_dump(mode="json")
        trajectory = self.learner_agent.trajectory.list_events(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            limit=240,
        )
        trajectory_summary = self.learner_agent.trajectory.summary(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            limit=2000,
        )
        trajectory_metrics = self.learner_agent.calibration.analyze(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
            limit=2000,
        )
        projects = self.projects.list_projects(tenant_id=tenant_id, owner_user_id=owner_user_id)
        raw_evidence = self.evidence.list_session(session_id, limit=240, tenant_id=tenant_id)
        evidence = [self._evidence_public(row) for row in raw_evidence]
        raw_artifacts = self.artifacts.list_session(
            session_id,
            include_content=False,
            tenant_id=tenant_id,
            all_versions=True,
        )
        artifacts = [self._artifact_public(row) for row in raw_artifacts]
        capabilities = self.capability_verification.verify(
            foundation_summary=foundation,
            trajectory_events=trajectory,
            evidence_items=raw_evidence,
        )
        work_sample = self.work_samples.public_state(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            session_id=session_id,
        )

        nodes: list[dict[str, Any]] = []
        connections: list[dict[str, Any]] = []
        foundation_state = "complete" if foundation.get("foundationComplete") else "active"
        nodes.append(
            self._node(
                "station:foundation",
                "workstation",
                "Foundation Workstation",
                zone="center",
                state=foundation_state,
                ref_id=str((foundation.get("currentTask") or {}).get("id") or "foundation"),
                data={
                    "progress": foundation.get("progress") or 0,
                    "currentTask": foundation.get("currentTask"),
                    "href": "/app/foundation",
                },
            )
        )
        nodes.append(
            self._node(
                "station:work-sample",
                "workstation",
                "Real Work Sample",
                zone="right",
                state=str(work_sample.get("status") or "locked"),
                ref_id=str(work_sample.get("id") or ""),
                data={"unlocked": bool(work_sample.get("unlocked")), "href": "/app/work-sample"},
            )
        )

        for index, project in enumerate(projects[:12]):
            project_id = str(project.get("project_id") or "")
            nodes.append(
                self._node(
                    f"project:{project_id}",
                    "project",
                    str(project.get("name") or "实践项目"),
                    zone="project_shelf",
                    state=str(project.get("status") or "draft"),
                    ref_id=project_id,
                    data={"order": index, "progress": project.get("progress") or {}, "updatedAt": project.get("updated_at")},
                )
            )

        for index, item in enumerate(evidence[:24]):
            evidence_id = str(item.get("id") or "")
            nodes.append(
                self._node(
                    f"evidence:{evidence_id}",
                    "evidence",
                    str(item.get("title") or "Evidence"),
                    zone="evidence_shelf",
                    state="verified" if item.get("verified") else "recorded",
                    ref_id=evidence_id,
                    data={
                        "order": index,
                        "verificationStatus": item.get("verificationStatus"),
                        "verificationConfidence": item.get("verificationConfidence"),
                    },
                )
            )

        for index, artifact in enumerate(artifacts[:24]):
            artifact_id = str(artifact.get("id") or "")
            version_id = str(artifact.get("versionId") or "")
            node_id = f"artifact:{artifact_id}:{version_id or artifact.get('version')}"
            nodes.append(
                self._node(
                    node_id,
                    "artifact",
                    f"{artifact.get('title') or 'Artifact'} · V{artifact.get('version') or 1}",
                    zone="project_table",
                    state="current" if artifact.get("isCurrent") else "history",
                    ref_id=artifact_id,
                    data={"order": index, **artifact},
                )
            )
            for evidence_id in artifact.get("evidenceIds") or []:
                connections.append(
                    {
                        "id": f"link:evidence:{evidence_id}:{node_id}",
                        "from": f"evidence:{evidence_id}",
                        "to": node_id,
                        "relation": "supports",
                        "authority": "server",
                    }
                )

        for index, capability in enumerate(capabilities.get("items") or []):
            capability_id = str(capability.get("capabilityId") or "")
            nodes.append(
                self._node(
                    f"capability:{capability_id}",
                    "capability",
                    str(capability.get("name") or capability_id),
                    zone="capability_field",
                    state=str(capability.get("verificationLevel") or "unobserved"),
                    ref_id=capability_id,
                    data={"order": index, **capability},
                )
            )
            for source in capability.get("sources") or []:
                if source.get("type") == "evidence" and source.get("id"):
                    connections.append(
                        {
                            "id": f"link:evidence:{source['id']}:capability:{capability_id}",
                            "from": f"evidence:{source['id']}",
                            "to": f"capability:{capability_id}",
                            "relation": "contributes_to",
                            "authority": "server",
                        }
                    )

        recent_trajectory = trajectory[-36:]
        for index, event in enumerate(recent_trajectory):
            event_id = str(event.get("event_id") or "")
            nodes.append(
                self._node(
                    f"trajectory:{event_id}",
                    "trajectory_event",
                    str(event.get("event_type") or "event"),
                    zone="trajectory_line",
                    state=str(event.get("outcome") or "neutral"),
                    ref_id=event_id,
                    data={
                        "order": index,
                        "taskId": event.get("task_id") or "",
                        "projectId": event.get("project_id") or "",
                        "evidenceId": event.get("evidence_id") or "",
                        "at": event.get("occurred_at") or "",
                    },
                )
            )

        return {
            "ok": True,
            "sceneStateVersion": SCENE_STATE_VERSION,
            "generatedAt": self._now(),
            "authority": {
                "source": "server",
                "readOnly": True,
                "clientMayPromoteCapability": False,
                "clientMayVerifyEvidence": False,
                "clientMayRewriteTrajectory": False,
                "allowedClientEffects": ["focus", "inspect", "filter", "camera", "animation"],
            },
            "identity": identity or {"userId": owner_user_id},
            "session": {"tenantId": tenant_id, "ownerUserId": owner_user_id, "sessionId": session_id},
            "foundation": foundation,
            "agent": {
                "state": agent_state,
                "trajectorySummary": trajectory_summary,
                "metrics": trajectory_metrics,
            },
            "trajectory": {"items": trajectory, "summary": trajectory_summary},
            "projects": {"items": projects, "count": len(projects)},
            "evidence": {"items": evidence, "count": len(evidence)},
            "artifacts": {"items": artifacts, "count": len(artifacts)},
            "capabilities": capabilities,
            "workSample": work_sample,
            "spatial": {
                "contract": "semantic_nodes_v1",
                "nodes": nodes,
                "connections": connections,
                "zones": ["center", "right", "project_shelf", "evidence_shelf", "project_table", "capability_field", "trajectory_line"],
            },
        }
