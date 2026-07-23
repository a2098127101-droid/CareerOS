from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def rowdict(row: Any) -> dict:
    if row is None:
        return {}
    mapping = getattr(row, "_mapping", row)
    return dict(mapping)


class SQLAlchemyRepo:
    def __init__(self, engine: Engine):
        self.engine = engine

    def one(self, sql: str, params: dict | None = None):
        with self.engine.connect() as conn:
            return conn.execute(text(sql), params or {}).mappings().first()

    def all(self, sql: str, params: dict | None = None):
        with self.engine.connect() as conn:
            return list(conn.execute(text(sql), params or {}).mappings().all())

    def execute(self, sql: str, params: dict | None = None) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(text(sql), params or {})
            return int(result.rowcount or 0)
