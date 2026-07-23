from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .lifecycle import workflow_snapshot
from .models import SessionState
from .workflow_templates import get_workflow_template, workflow_template_from_record


class WorkflowStore:
    """Persisted workflow runtime backed by preset-aware templates.

    Existing v0.x sessions remain readable. New sessions bind to a template_id derived from the
    tenant Product Preset, while explicit completion history remains authoritative and is never
    downgraded by state inference.
    """

    def __init__(self, db_path: str, template_registry=None):
        self.db_path = Path(db_path)
        self.template_registry = template_registry
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        from .migrations import run_migrations
        run_migrations(str(self.db_path))

    def _template(self, preset_id: str, tenant_id: str = ""):
        if self.template_registry is not None and tenant_id:
            record = self.template_registry.active_workflow(tenant_id=tenant_id, preset_id=preset_id)
            if record:
                return workflow_template_from_record(record)
        return get_workflow_template(preset_id)

    def _create_instance(self, conn: sqlite3.Connection, state: SessionState, preset_id: str) -> tuple[str, str]:
        template = self._template(preset_id, state.tenant_id)
        workflow_id = f"WF-{uuid4().hex[:12].upper()}"
        conn.execute(
            "INSERT INTO workflow_instances(workflow_id,tenant_id,session_id,template_id) VALUES(?,?,?,?)",
            (workflow_id, state.tenant_id, state.session_id, template.template_id),
        )
        for step in template.steps:
            conn.execute(
                """INSERT INTO workflow_steps(workflow_step_id,workflow_id,tenant_id,session_id,step_id,step_index,label,status,metadata_json)
                VALUES(?,?,?,?,?,?,?,'locked',?)""",
                (
                    f"WFS-{uuid4().hex[:12].upper()}", workflow_id, state.tenant_id, state.session_id,
                    step.step_id, step.index, step.label,
                    json.dumps({
                        "description": step.description,
                        "required_evidence": step.required_evidence,
                        "required_artifact": step.required_artifact,
                        "template_id": template.template_id,
                    }, ensure_ascii=False),
                ),
            )
        return workflow_id, template.template_id

    def ensure(self, state: SessionState, artifact_kinds: set[str] | None = None, *, preset_id: str = "career_development") -> dict:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT workflow_id,template_id FROM workflow_instances WHERE session_id=? AND tenant_id=?",
                (state.session_id, state.tenant_id),
            ).fetchone()
            if not row:
                self._create_instance(conn, state, preset_id)
                conn.commit()
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
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT workflow_id,template_id FROM workflow_instances WHERE session_id=? AND tenant_id=?",
                (state.session_id, state.tenant_id),
            ).fetchone()
            if not row:
                workflow_id, _ = self._create_instance(conn, state, preset_id)
            else:
                workflow_id = row["workflow_id"]

            rows = conn.execute(
                "SELECT step_id,step_index,status FROM workflow_steps WHERE workflow_id=? ORDER BY step_index",
                (workflow_id,),
            ).fetchall()
            now = datetime.now(timezone.utc).isoformat()
            for r in rows:
                if r["step_id"] in completed_ids and r["status"] != "completed":
                    conn.execute(
                        """UPDATE workflow_steps SET status='completed',started_at=COALESCE(started_at,?),completed_at=COALESCE(completed_at,?),
                        completed_by=?,source_type=?,source_id=?,updated_at=CURRENT_TIMESTAMP WHERE workflow_id=? AND step_id=?""",
                        (now, now, completed_by, source_type, source_id, workflow_id, r["step_id"]),
                    )

            rows = conn.execute(
                "SELECT step_id,step_index,status FROM workflow_steps WHERE workflow_id=? ORDER BY step_index",
                (workflow_id,),
            ).fetchall()
            first_unfinished = next((r["step_id"] for r in rows if r["status"] != "completed"), rows[-1]["step_id"] if rows else "")
            has_started = any(r["status"] == "completed" for r in rows)
            for r in rows:
                if r["status"] == "completed":
                    continue
                status = "current" if r["step_id"] == first_unfinished else ("available" if has_started else "locked")
                conn.execute(
                    "UPDATE workflow_steps SET status=?,started_at=CASE WHEN ?='current' THEN COALESCE(started_at,?) ELSE started_at END,updated_at=CURRENT_TIMESTAMP WHERE workflow_id=? AND step_id=?",
                    (status, status, now, workflow_id, r["step_id"]),
                )
            completed_count = conn.execute(
                "SELECT COUNT(*) FROM workflow_steps WHERE workflow_id=? AND status='completed'", (workflow_id,)
            ).fetchone()[0]
            total = max(1, len(rows))
            conn.execute(
                "UPDATE workflow_instances SET tenant_id=?,current_step_id=?,progress=?,updated_at=CURRENT_TIMESTAMP WHERE workflow_id=?",
                (state.tenant_id, first_unfinished, int(completed_count / total * 100), workflow_id),
            )
            conn.commit()
        return self.snapshot(state.session_id, tenant_id=state.tenant_id)

    def mark_completed(
        self,
        session_id: str,
        step_id: str,
        *,
        tenant_id: str,
        completed_by: str = "system",
        source_type: str = "manual",
        source_id: str = "",
        metadata: dict | None = None,
    ) -> dict:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT workflow_id FROM workflow_instances WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)
            ).fetchone()
            if not row:
                raise KeyError(session_id)
            workflow_id = row["workflow_id"]
            now = datetime.now(timezone.utc).isoformat()
            changed = conn.execute(
                """UPDATE workflow_steps SET status='completed',started_at=COALESCE(started_at,?),completed_at=COALESCE(completed_at,?),
                completed_by=?,source_type=?,source_id=?,metadata_json=?,updated_at=CURRENT_TIMESTAMP
                WHERE workflow_id=? AND step_id=?""",
                (now, now, completed_by, source_type, source_id, json.dumps(metadata or {}, ensure_ascii=False), workflow_id, step_id),
            ).rowcount
            if not changed:
                raise KeyError(step_id)
            rows = conn.execute(
                "SELECT step_id,status FROM workflow_steps WHERE workflow_id=? ORDER BY step_index", (workflow_id,)
            ).fetchall()
            next_id = next((r["step_id"] for r in rows if r["status"] != "completed"), step_id)
            for r in rows:
                if r["status"] == "completed":
                    continue
                conn.execute(
                    "UPDATE workflow_steps SET status=? WHERE workflow_id=? AND step_id=?",
                    ("current" if r["step_id"] == next_id else "available", workflow_id, r["step_id"]),
                )
            count = conn.execute("SELECT COUNT(*) FROM workflow_steps WHERE workflow_id=? AND status='completed'", (workflow_id,)).fetchone()[0]
            conn.execute(
                "UPDATE workflow_instances SET current_step_id=?,progress=?,updated_at=CURRENT_TIMESTAMP WHERE workflow_id=?",
                (next_id, int(count / max(1, len(rows)) * 100), workflow_id),
            )
            conn.commit()
        return self.snapshot(session_id, tenant_id=tenant_id)

    def snapshot(self, session_id: str, *, tenant_id: str | None = None) -> dict:
        sql = "SELECT * FROM workflow_instances WHERE session_id=?"
        params: list[object] = [session_id]
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        with self._connect() as conn:
            inst = conn.execute(sql, tuple(params)).fetchone()
            if not inst:
                raise KeyError(session_id)
            rows = conn.execute(
                "SELECT * FROM workflow_steps WHERE workflow_id=? ORDER BY step_index", (inst["workflow_id"],)
            ).fetchall()
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
            "workflow_id": inst["workflow_id"],
            "session_id": inst["session_id"],
            "template_id": inst["template_id"] if "template_id" in inst.keys() else "career_development_v1",
            "completed": sum(1 for x in steps if x["status"] == "completed"),
            "total": len(steps),
            "progress": int(inst["progress"]),
            "current_step": current,
            "steps": steps,
            "created_at": inst["created_at"],
            "updated_at": inst["updated_at"],
        }

    def delete_session(self, session_id: str, *, tenant_id: str) -> dict:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT workflow_id FROM workflow_instances WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)).fetchall()
            ids = [r[0] for r in rows]
            steps = 0
            for wid in ids:
                steps += conn.execute("DELETE FROM workflow_steps WHERE workflow_id=? AND tenant_id=?", (wid, tenant_id)).rowcount
            instances = conn.execute("DELETE FROM workflow_instances WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)).rowcount
            conn.commit()
            return {"instances": int(instances), "steps": int(steps)}
