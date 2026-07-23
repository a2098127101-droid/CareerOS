from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import MetaData, Table, and_, insert, select, update, text
from sqlalchemy.engine import Engine

from ...models import SessionState


class PostgresSessionRepository:
    """SQLAlchemy Core session repository usable with PostgreSQL-compatible engines.

    This is the first parity adapter in the staged v1 migration. The full PostgreSQL container is
    intentionally not enabled until the remaining repositories reach parity.
    """

    def __init__(self, engine: Engine, metadata: MetaData):
        self.engine = engine
        self.table: Table = metadata.tables["sessions"]

    def create(self, *, tenant_id: str = "demo-org", student_user_id: str = "", class_id: str = "default", student_id: str = "") -> SessionState:
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

    def save(self, state: SessionState) -> None:
        values = {
            "session_id": state.session_id,
            "payload": state.model_dump_json(),
            "tenant_id": state.tenant_id,
            "student_user_id": state.student_user_id,
            "class_id": state.class_id,
        }
        with self.engine.begin() as conn:
            exists = conn.execute(select(self.table.c.session_id).where(self.table.c.session_id == state.session_id)).first()
            if exists:
                conn.execute(
                    update(self.table)
                    .where(self.table.c.session_id == state.session_id)
                    .values(**values, updated_at=text("CURRENT_TIMESTAMP"))
                )
            else:
                conn.execute(insert(self.table).values(**values))

    def metadata(self, session_id: str) -> dict:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(
                    self.table.c.session_id,
                    self.table.c.tenant_id,
                    self.table.c.student_user_id,
                    self.table.c.class_id,
                    self.table.c.created_at,
                    self.table.c.updated_at,
                ).where(self.table.c.session_id == session_id)
            ).mappings().first()
        if not row:
            raise KeyError(session_id)
        return dict(row)

    def assign_owner(
        self, session_id: str, *, tenant_id: str, student_user_id: str, class_id: str = "default"
    ) -> SessionState:
        state = self.get(session_id)
        state.tenant_id = tenant_id
        state.student_user_id = student_user_id
        state.class_id = class_id or "default"
        self.save(state)
        return state

    def get(self, session_id: str, *, tenant_id: str | None = None, student_user_id: str | None = None) -> SessionState:
        clauses = [self.table.c.session_id == session_id]
        if tenant_id is not None:
            clauses.append(self.table.c.tenant_id == tenant_id)
        if student_user_id is not None:
            clauses.append(self.table.c.student_user_id == student_user_id)
        with self.engine.connect() as conn:
            row = conn.execute(select(self.table.c.payload).where(and_(*clauses))).first()
        if not row:
            raise KeyError(session_id)
        return SessionState.model_validate(json.loads(row.payload))

    def list(self, limit: int = 200, *, tenant_id: str | None = None, class_id: str | None = None, student_user_id: str | None = None):
        clauses = []
        if tenant_id is not None:
            clauses.append(self.table.c.tenant_id == tenant_id)
        if class_id:
            clauses.append(self.table.c.class_id == class_id)
        if student_user_id is not None:
            clauses.append(self.table.c.student_user_id == student_user_id)
        stmt = select(self.table.c.payload, self.table.c.updated_at)
        if clauses:
            stmt = stmt.where(and_(*clauses))
        stmt = stmt.order_by(self.table.c.updated_at.desc()).limit(limit)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).all()
        return [(SessionState.model_validate(json.loads(row.payload)), str(row.updated_at or "")) for row in rows]

    def delete_session(self, session_id: str, *, tenant_id: str) -> bool:
        return bool(self.execute("DELETE FROM sessions WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id}))
