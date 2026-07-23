from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4

from .models import SessionState


class SessionStore:
    """Session persistence with indexed tenant/owner columns.

    The legacy JSON payload is preserved for backwards compatibility, while tenant/owner/class
    identifiers are duplicated into real columns so authorization and filtering happen in SQL.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
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

    def create(
        self,
        *,
        tenant_id: str = "demo-org",
        student_user_id: str = "",
        class_id: str = "default",
        student_id: str = "",
    ) -> SessionState:
        session_id = str(uuid4())
        state = SessionState(
            session_id=session_id,
            tenant_id=tenant_id,
            class_id=class_id or "default",
            student_id=student_id or session_id,
            student_user_id=student_user_id,
        )
        self.save(state)
        return state

    def get(
        self,
        session_id: str,
        *,
        tenant_id: str | None = None,
        student_user_id: str | None = None,
    ) -> SessionState:
        sql = "SELECT payload FROM sessions WHERE session_id=?"
        params: list[str] = [session_id]
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        if student_user_id is not None:
            sql += " AND student_user_id=?"
            params.append(student_user_id)
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        if not row:
            raise KeyError(session_id)
        return SessionState.model_validate(json.loads(row["payload"]))

    def metadata(self, session_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT session_id,tenant_id,student_user_id,class_id,created_at,updated_at FROM sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
        if not row:
            raise KeyError(session_id)
        return dict(row)

    def save(self, state: SessionState) -> None:
        payload = state.model_dump_json()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO sessions(session_id,payload,tenant_id,student_user_id,class_id,created_at,updated_at)
                VALUES(?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)
                ON CONFLICT(session_id) DO UPDATE SET
                    payload=excluded.payload,
                    tenant_id=excluded.tenant_id,
                    student_user_id=excluded.student_user_id,
                    class_id=excluded.class_id,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    state.session_id,
                    payload,
                    state.tenant_id or "demo-org",
                    state.student_user_id or "",
                    state.class_id or "default",
                ),
            )
            conn.commit()

    def assign_owner(self, session_id: str, *, tenant_id: str, student_user_id: str, class_id: str = "default") -> SessionState:
        state = self.get(session_id)
        state.tenant_id = tenant_id
        state.student_user_id = student_user_id
        state.class_id = class_id or "default"
        self.save(state)
        return state

    def list(
        self,
        limit: int = 200,
        *,
        tenant_id: str | None = None,
        class_id: str | None = None,
        student_user_id: str | None = None,
    ) -> list[tuple[SessionState, str]]:
        clauses: list[str] = []
        params: list[object] = []
        if tenant_id is not None:
            clauses.append("tenant_id=?")
            params.append(tenant_id)
        if class_id:
            clauses.append("class_id=?")
            params.append(class_id)
        if student_user_id is not None:
            clauses.append("student_user_id=?")
            params.append(student_user_id)
        sql = "SELECT payload,updated_at FROM sessions"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        result: list[tuple[SessionState, str]] = []
        for row in rows:
            try:
                result.append((SessionState.model_validate(json.loads(row["payload"])), row["updated_at"]))
            except Exception:
                continue
        return result

    def delete_session(self, session_id: str, *, tenant_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM sessions WHERE session_id=? AND tenant_id=?", (session_id, tenant_id))
            conn.commit()
            return bool(cur.rowcount)
