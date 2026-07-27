from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4


class CollaborationStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Ensure the canonical SQLite compatibility schema via the centralized migration layer.

        Store modules no longer own CREATE TABLE/CREATE INDEX DDL. The checked-in schema manifest
        and versioned migrations are the single compatibility source used by both local SQLite and
        Alembic/PostgreSQL provisioning.
        """
        from .migrations import run_migrations
        run_migrations(str(self.db_path))

    def add_feedback(
        self,
        session_id: str,
        content: str,
        teacher_name: str = "Advisor",
        priority: str = "normal",
        *,
        tenant_id: str = "demo-org",
        teacher_user_id: str = "",
    ) -> dict:
        feedback_id = f"FB-{uuid4().hex[:10].upper()}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO teacher_feedback(feedback_id,session_id,tenant_id,teacher_user_id,teacher_name,content,priority)
                VALUES(?,?,?,?,?,?,?)""",
                (feedback_id, session_id, tenant_id, teacher_user_id, teacher_name[:80], content.strip(), priority),
            )
            conn.commit()
        return self.get_feedback(feedback_id, tenant_id=tenant_id)

    def get_feedback(self, feedback_id: str, *, tenant_id: str | None = None) -> dict:
        sql = "SELECT * FROM teacher_feedback WHERE feedback_id=?"
        params: list[str] = [feedback_id]
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        if not row:
            raise KeyError(feedback_id)
        return dict(row)

    def list_feedback(self, session_id: str, status: str | None = None, *, tenant_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM teacher_feedback WHERE session_id=?"
        params: list[object] = [session_id]
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        if status:
            sql += " AND status=?"
            params.append(status)
        sql += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def resolve_feedback(self, feedback_id: str, *, tenant_id: str | None = None) -> None:
        sql = "UPDATE teacher_feedback SET status='resolved',resolved_at=CURRENT_TIMESTAMP WHERE feedback_id=?"
        params: list[str] = [feedback_id]
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        with self._lock, self._connect() as conn:
            cur = conn.execute(sql, tuple(params))
            if cur.rowcount == 0:
                raise KeyError(feedback_id)
            conn.commit()

    def ensure_task(
        self,
        title: str,
        task_type: str,
        session_id: str = "",
        tenant_id: str = "demo-org",
        priority: str = "normal",
        source: str = "system",
        payload: dict | None = None,
        owner_user_id: str = "",
    ) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM ai_tasks WHERE tenant_id=? AND session_id=? AND task_type=?
                AND status IN ('todo','doing') ORDER BY created_at DESC LIMIT 1""",
                (tenant_id, session_id, task_type),
            ).fetchone()
        if row:
            return self._task_row(row)
        return self.create_task(title, task_type, session_id, tenant_id, priority, source, payload, owner_user_id=owner_user_id)

    def create_task(
        self,
        title: str,
        task_type: str,
        session_id: str = "",
        tenant_id: str = "demo-org",
        priority: str = "normal",
        source: str = "system",
        payload: dict | None = None,
        *,
        owner_user_id: str = "",
        task_id: str | None = None,
    ) -> dict:
        task_id = task_id or f"TASK-{uuid4().hex[:10].upper()}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO ai_tasks(task_id,session_id,tenant_id,owner_user_id,title,task_type,priority,source,payload_json)
                VALUES(?,?,?,?,?,?,?,?,?)""",
                (task_id, session_id, tenant_id, owner_user_id, title, task_type, priority, source, json.dumps(payload or {}, ensure_ascii=False)),
            )
            conn.commit()
        return self.get_task(task_id, tenant_id=tenant_id)

    def get_task(self, task_id: str, *, tenant_id: str | None = None) -> dict:
        sql = "SELECT * FROM ai_tasks WHERE task_id=?"
        params: list[str] = [task_id]
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        if not row:
            raise KeyError(task_id)
        return self._task_row(row)

    def list_tasks(
        self,
        tenant_id: str = "demo-org",
        status: str | None = None,
        limit: int = 200,
        *,
        session_id: str | None = None,
        owner_user_id: str | None = None,
    ) -> list[dict]:
        sql = "SELECT * FROM ai_tasks WHERE tenant_id=?"
        params: list[object] = [tenant_id]
        if status:
            sql += " AND status=?"
            params.append(status)
        if session_id is not None:
            sql += " AND session_id=?"
            params.append(session_id)
        if owner_user_id is not None:
            sql += " AND owner_user_id=?"
            params.append(owner_user_id)
        sql += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [self._task_row(r) for r in rows]

    def update_task(
        self, task_id: str, status: str | None = None, priority: str | None = None, *,
        tenant_id: str | None = None, expected_version: int | None = None, title: str | None = None,
        task_type: str | None = None, source: str | None = None, payload: dict | None = None,
    ) -> dict:
        fields: list[str] = []
        params: list[object] = []
        current = self.get_task(task_id, tenant_id=tenant_id)
        actual = int(current.get("version") or 1)
        if expected_version is not None and expected_version != actual:
            from .unified_runtime_store import RuntimeVersionConflict
            raise RuntimeVersionConflict(task_id, expected_version, actual)
        for column, value in (("status", status), ("priority", priority), ("title", title), ("task_type", task_type), ("source", source)):
            if value is not None:
                fields.append(f"{column}=?")
                params.append(value)
        if payload is not None:
            fields.append("payload_json=?")
            params.append(json.dumps(payload, ensure_ascii=False))
        if not fields:
            return current
        if status in {"done", "completed"}:
            fields.append("completed_at=CURRENT_TIMESTAMP")
        elif status is not None:
            fields.append("completed_at=NULL")
        fields.extend(["version=version+1", "updated_at=CURRENT_TIMESTAMP"])
        sql = f"UPDATE ai_tasks SET {', '.join(fields)} WHERE task_id=?"
        params.append(task_id)
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        with self._lock, self._connect() as conn:
            cur = conn.execute(sql, tuple(params))
            if cur.rowcount == 0:
                raise KeyError(task_id)
            conn.commit()
        return self.get_task(task_id, tenant_id=tenant_id)

    def complete_matching(self, session_id: str, task_type: str, *, tenant_id: str | None = None) -> None:
        sql = "UPDATE ai_tasks SET status='done',updated_at=CURRENT_TIMESTAMP WHERE session_id=? AND task_type=? AND status!='done'"
        params: list[str] = [session_id, task_type]
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        with self._lock, self._connect() as conn:
            conn.execute(sql, tuple(params))
            conn.commit()

    @staticmethod
    def _task_row(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json") or "{}")
        return data

    def delete_session(self, session_id: str, *, tenant_id: str) -> dict:
        with self._lock, self._connect() as conn:
            feedback = conn.execute("DELETE FROM teacher_feedback WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)).rowcount
            tasks = conn.execute("DELETE FROM ai_tasks WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)).rowcount
            conn.commit()
            return {"feedback": int(feedback), "tasks": int(tasks)}
