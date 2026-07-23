from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ...lifecycle import workflow_snapshot
from ...models import SessionState
from ...workflow_templates import get_workflow_template, workflow_template_from_record
from ..sqlalchemy_common import SQLAlchemyRepo


class PostgresWorkflowRepository(SQLAlchemyRepo):
    def __init__(self, engine: Engine, template_registry=None):
        super().__init__(engine)
        self.template_registry = template_registry

    def _template(self, preset_id: str, tenant_id: str = ""):
        if self.template_registry is not None and tenant_id:
            record = self.template_registry.active_workflow(tenant_id=tenant_id, preset_id=preset_id)
            if record:
                return workflow_template_from_record(record)
        return get_workflow_template(preset_id)

    def _create_instance(self, conn, state: SessionState, preset_id: str) -> tuple[str, str]:
        template = self._template(preset_id, state.tenant_id)
        workflow_id = f"WF-{uuid4().hex[:12].upper()}"
        conn.execute(text(
            "INSERT INTO workflow_instances(workflow_id,tenant_id,session_id,template_id) VALUES(:id,:tenant,:session,:template)"
        ), {"id": workflow_id, "tenant": state.tenant_id, "session": state.session_id, "template": template.template_id})
        for step in template.steps:
            conn.execute(text("""INSERT INTO workflow_steps(
                workflow_step_id,workflow_id,tenant_id,session_id,step_id,step_index,label,status,metadata_json
            ) VALUES(:id,:wid,:tenant,:session,:step,:idx,:label,'locked',:meta)"""), {
                "id": f"WFS-{uuid4().hex[:12].upper()}", "wid": workflow_id, "tenant": state.tenant_id,
                "session": state.session_id, "step": step.step_id, "idx": step.index, "label": step.label,
                "meta": json.dumps({
                    "description": step.description,
                    "required_evidence": step.required_evidence,
                    "required_artifact": step.required_artifact,
                    "template_id": template.template_id,
                }, ensure_ascii=False),
            })
        return workflow_id, template.template_id

    def ensure(self, state: SessionState, artifact_kinds: set[str] | None = None, *, preset_id: str = "career_development") -> dict:
        with self.engine.begin() as conn:
            row = conn.execute(text(
                "SELECT workflow_id,template_id FROM workflow_instances WHERE session_id=:session AND tenant_id=:tenant"
            ), {"session": state.session_id, "tenant": state.tenant_id}).mappings().first()
            if not row:
                self._create_instance(conn, state, preset_id)
        self.sync_from_state(state, artifact_kinds=artifact_kinds or set(), source_type="legacy_state", preset_id=preset_id)
        return self.snapshot(state.session_id, tenant_id=state.tenant_id)

    def sync_from_state(
        self,
        state: SessionState,
        artifact_kinds: set[str] | None = None,
        *,
        source_type: str = "state_sync",
        source_id: str = "",
        completed_by: str = "system",
        preset_id: str = "career_development",
    ) -> dict:
        template = self._template(preset_id, state.tenant_id)
        inferred = workflow_snapshot(state, artifact_kinds or set(), preset_id=preset_id, template=template)
        completed_ids = {x["id"] for x in inferred["steps"] if x["status"] == "completed"}
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            row = conn.execute(text(
                "SELECT workflow_id,template_id FROM workflow_instances WHERE session_id=:session AND tenant_id=:tenant"
            ), {"session": state.session_id, "tenant": state.tenant_id}).mappings().first()
            if not row:
                workflow_id, _ = self._create_instance(conn, state, preset_id)
            else:
                workflow_id = row["workflow_id"]
            rows = conn.execute(text(
                "SELECT step_id,step_index,status FROM workflow_steps WHERE workflow_id=:wid ORDER BY step_index"
            ), {"wid": workflow_id}).mappings().all()
            for r in rows:
                if r["step_id"] in completed_ids and r["status"] != "completed":
                    conn.execute(text("""UPDATE workflow_steps SET status='completed',started_at=COALESCE(started_at,:now),
                    completed_at=COALESCE(completed_at,:now),completed_by=:by,source_type=:stype,source_id=:sid,
                    updated_at=CURRENT_TIMESTAMP WHERE workflow_id=:wid AND step_id=:step"""), {
                        "now": now, "by": completed_by, "stype": source_type, "sid": source_id,
                        "wid": workflow_id, "step": r["step_id"],
                    })
            rows = conn.execute(text(
                "SELECT step_id,step_index,status FROM workflow_steps WHERE workflow_id=:wid ORDER BY step_index"
            ), {"wid": workflow_id}).mappings().all()
            first_unfinished = next((r["step_id"] for r in rows if r["status"] != "completed"), rows[-1]["step_id"] if rows else "")
            has_started = any(r["status"] == "completed" for r in rows)
            for r in rows:
                if r["status"] == "completed":
                    continue
                status = "current" if r["step_id"] == first_unfinished else ("available" if has_started else "locked")
                conn.execute(text("""UPDATE workflow_steps SET status=:status,
                started_at=CASE WHEN :status='current' THEN COALESCE(started_at,:now) ELSE started_at END,
                updated_at=CURRENT_TIMESTAMP WHERE workflow_id=:wid AND step_id=:step"""), {
                    "status": status, "now": now, "wid": workflow_id, "step": r["step_id"],
                })
            count = conn.execute(text(
                "SELECT COUNT(*) AS c FROM workflow_steps WHERE workflow_id=:wid AND status='completed'"
            ), {"wid": workflow_id}).mappings().first()["c"]
            conn.execute(text("""UPDATE workflow_instances SET tenant_id=:tenant,current_step_id=:step,progress=:progress,
            updated_at=CURRENT_TIMESTAMP WHERE workflow_id=:wid"""), {
                "tenant": state.tenant_id, "step": first_unfinished,
                "progress": int(count / max(1, len(rows)) * 100), "wid": workflow_id,
            })
        return self.snapshot(state.session_id, tenant_id=state.tenant_id)

    def mark_completed(self, session_id: str, step_id: str, *, tenant_id: str, completed_by: str = "system",
                       source_type: str = "manual", source_id: str = "", metadata: dict | None = None) -> dict:
        now = datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            row = conn.execute(text(
                "SELECT workflow_id FROM workflow_instances WHERE session_id=:session AND tenant_id=:tenant"
            ), {"session": session_id, "tenant": tenant_id}).mappings().first()
            if not row:
                raise KeyError(session_id)
            wid = row["workflow_id"]
            result = conn.execute(text("""UPDATE workflow_steps SET status='completed',started_at=COALESCE(started_at,:now),
            completed_at=COALESCE(completed_at,:now),completed_by=:by,source_type=:stype,source_id=:sid,metadata_json=:meta,
            updated_at=CURRENT_TIMESTAMP WHERE workflow_id=:wid AND step_id=:step"""), {
                "now": now, "by": completed_by, "stype": source_type, "sid": source_id,
                "meta": json.dumps(metadata or {}, ensure_ascii=False), "wid": wid, "step": step_id,
            })
            if not result.rowcount:
                raise KeyError(step_id)
            rows = conn.execute(text(
                "SELECT step_id,status FROM workflow_steps WHERE workflow_id=:wid ORDER BY step_index"
            ), {"wid": wid}).mappings().all()
            next_id = next((r["step_id"] for r in rows if r["status"] != "completed"), step_id)
            for r in rows:
                if r["status"] != "completed":
                    conn.execute(text(
                        "UPDATE workflow_steps SET status=:status WHERE workflow_id=:wid AND step_id=:step"
                    ), {"status": "current" if r["step_id"] == next_id else "available", "wid": wid, "step": r["step_id"]})
            count = conn.execute(text(
                "SELECT COUNT(*) AS c FROM workflow_steps WHERE workflow_id=:wid AND status='completed'"
            ), {"wid": wid}).mappings().first()["c"]
            conn.execute(text(
                "UPDATE workflow_instances SET current_step_id=:step,progress=:progress,updated_at=CURRENT_TIMESTAMP WHERE workflow_id=:wid"
            ), {"step": next_id, "progress": int(count / max(1, len(rows)) * 100), "wid": wid})
        return self.snapshot(session_id, tenant_id=tenant_id)

    def snapshot(self, session_id: str, *, tenant_id: str | None = None) -> dict:
        sql = "SELECT * FROM workflow_instances WHERE session_id=:session"
        params = {"session": session_id}
        if tenant_id is not None:
            sql += " AND tenant_id=:tenant"
            params["tenant"] = tenant_id
        inst = self.one(sql, params)
        if not inst:
            raise KeyError(session_id)
        rows = self.all("SELECT * FROM workflow_steps WHERE workflow_id=:wid ORDER BY step_index", {"wid": inst["workflow_id"]})
        steps = []
        for r in rows:
            item = dict(r)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            except Exception:
                item["metadata"] = {}
            steps.append(item)
        current = next((x for x in steps if x["status"] == "current"), steps[-1] if steps else None)
        return {
            "workflow_id": inst["workflow_id"], "session_id": inst["session_id"],
            "template_id": inst.get("template_id") or "career_development_v1",
            "completed": sum(1 for x in steps if x["status"] == "completed"), "total": len(steps),
            "progress": int(inst["progress"]), "current_step": current, "steps": steps,
            "created_at": inst["created_at"], "updated_at": inst["updated_at"],
        }

    def delete_session(self, session_id: str, *, tenant_id: str) -> dict:
        rows = self.all("SELECT workflow_id FROM workflow_instances WHERE session_id=:session AND tenant_id=:tenant",
                        {"session": session_id, "tenant": tenant_id})
        steps = 0
        for row in rows:
            steps += self.execute("DELETE FROM workflow_steps WHERE workflow_id=:wid AND tenant_id=:tenant",
                                  {"wid": row["workflow_id"], "tenant": tenant_id})
        instances = self.execute("DELETE FROM workflow_instances WHERE session_id=:session AND tenant_id=:tenant",
                                 {"session": session_id, "tenant": tenant_id})
        return {"instances": instances, "steps": steps}
