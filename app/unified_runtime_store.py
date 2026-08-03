from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class RuntimeVersionConflict(RuntimeError):
    def __init__(self, entity_id: str, expected: int | None, actual: int | None):
        super().__init__(f"version conflict for {entity_id}: expected={expected}, actual={actual}")
        self.entity_id = entity_id
        self.expected = expected
        self.actual = actual


class UnifiedRuntimeStore:
    """Compatibility/runtime-state repository with owner isolation and optimistic concurrency.

    v1.4 narrows this store to runtime/cache-style entities. Canonical business domains should be
    accessed through their dedicated services. Every private row is keyed by tenant + owner + type
    + entity id, so identical client IDs from different users cannot collide.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        from .migrations import run_migrations
        run_migrations(str(self.db_path))

    @staticmethod
    def _decode(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        data = dict(row)
        payload = json.loads(data.pop("payload_json") or "{}")
        payload.setdefault("id", data["entity_id"])
        payload.setdefault("entity_type", data["entity_type"])
        payload.setdefault("createdAt", str(data.get("created_at") or ""))
        payload["updatedAt"] = str(data.get("updated_at") or payload.get("updatedAt") or "")
        payload["_version"] = int(data.get("version") or 1)
        payload["_revision"] = int(data.get("revision") or 0)
        payload["_ownerUserId"] = str(data.get("owner_user_id") or "")
        payload["_deleted"] = bool(data.get("deleted_at"))
        return payload

    @staticmethod
    def _clean_payload(payload: dict[str, Any], entity_id: str) -> str:
        clean = dict(payload or {})
        clean["id"] = entity_id
        for key in ("entity_type", "_version", "_revision", "_ownerUserId", "_deleted"):
            clean.pop(key, None)
        return json.dumps(clean, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _next_revision(conn: sqlite3.Connection, tenant_id: str) -> int:
        conn.execute(
            "INSERT OR IGNORE INTO unified_runtime_revisions(tenant_id,revision) VALUES(?,0)",
            (tenant_id,),
        )
        conn.execute(
            "UPDATE unified_runtime_revisions SET revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE tenant_id=?",
            (tenant_id,),
        )
        row = conn.execute(
            "SELECT revision FROM unified_runtime_revisions WHERE tenant_id=?", (tenant_id,)
        ).fetchone()
        return int(row[0] if row else 0)

    def current_revision(self, *, tenant_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT revision FROM unified_runtime_revisions WHERE tenant_id=?", (tenant_id,)
            ).fetchone()
        return int(row[0] if row else 0)

    def list(
        self,
        *,
        tenant_id: str,
        entity_type: str,
        owner_user_id: str | None = None,
        limit: int = 5000,
        include_deleted: bool = False,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM unified_runtime_entities WHERE tenant_id=? AND entity_type=?"
        params: list[Any] = [tenant_id, entity_type]
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        if owner_user_id is not None:
            sql += " AND owner_user_id=?"
            params.append(owner_user_id)
        sql += " ORDER BY revision ASC,owner_user_id ASC,entity_id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [self._decode(r) for r in rows]

    def list_all(
        self,
        *,
        tenant_id: str,
        entity_type: str,
        owner_user_id: str | None = None,
        include_deleted: bool = False,
        page_size: int = 1000,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        offset = 0
        while True:
            page = self.list(
                tenant_id=tenant_id,
                entity_type=entity_type,
                owner_user_id=owner_user_id,
                limit=page_size,
                include_deleted=include_deleted,
                offset=offset,
            )
            out.extend(page)
            if len(page) < page_size:
                break
            offset += len(page)
        return out

    def get(
        self,
        *,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        owner_user_id: str | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any]:
        sql = "SELECT * FROM unified_runtime_entities WHERE tenant_id=? AND entity_type=? AND entity_id=?"
        params: list[Any] = [tenant_id, entity_type, entity_id]
        if owner_user_id is not None:
            sql += " AND owner_user_id=?"
            params.append(owner_user_id)
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        if not rows:
            raise KeyError(entity_id)
        if len(rows) > 1 and owner_user_id is None:
            raise KeyError(f"ambiguous entity without owner scope: {entity_id}")
        return self._decode(rows[0])

    def upsert(
        self,
        *,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any],
        owner_user_id: str = "",
        expected_version: int | None = None,
        updated_by: str = "",
    ) -> dict[str, Any]:
        raw = self._clean_payload(payload, entity_id)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """SELECT version FROM unified_runtime_entities
                WHERE tenant_id=? AND owner_user_id=? AND entity_type=? AND entity_id=?""",
                (tenant_id, owner_user_id, entity_type, entity_id),
            ).fetchone()
            actual = int(row["version"]) if row else None
            if expected_version is not None and actual != expected_version:
                raise RuntimeVersionConflict(entity_id, expected_version, actual)
            revision = self._next_revision(conn, tenant_id)
            if row:
                version = actual + 1
                conn.execute(
                    """UPDATE unified_runtime_entities SET payload_json=?,version=?,revision=?,updated_by=?,
                    deleted_at=NULL,updated_at=CURRENT_TIMESTAMP
                    WHERE tenant_id=? AND owner_user_id=? AND entity_type=? AND entity_id=?""",
                    (raw, version, revision, updated_by, tenant_id, owner_user_id, entity_type, entity_id),
                )
            else:
                version = 1
                conn.execute(
                    """INSERT INTO unified_runtime_entities
                    (tenant_id,owner_user_id,entity_type,entity_id,payload_json,version,revision,updated_by,deleted_at,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""",
                    (tenant_id, owner_user_id, entity_type, entity_id, raw, version, revision, updated_by),
                )
            conn.commit()
        return self.get(
            tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
            owner_user_id=owner_user_id,
        )

    def delete(
        self,
        *,
        tenant_id: str,
        entity_type: str,
        entity_id: str,
        owner_user_id: str = "",
        expected_version: int | None = None,
        hard: bool = False,
        updated_by: str = "",
    ) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """SELECT version,deleted_at FROM unified_runtime_entities
                WHERE tenant_id=? AND owner_user_id=? AND entity_type=? AND entity_id=?""",
                (tenant_id, owner_user_id, entity_type, entity_id),
            ).fetchone()
            if not row:
                return False
            actual = int(row["version"])
            if expected_version is not None and actual != expected_version:
                raise RuntimeVersionConflict(entity_id, expected_version, actual)
            if hard:
                conn.execute(
                    "DELETE FROM unified_runtime_entities WHERE tenant_id=? AND owner_user_id=? AND entity_type=? AND entity_id=?",
                    (tenant_id, owner_user_id, entity_type, entity_id),
                )
                self._next_revision(conn, tenant_id)
            else:
                revision = self._next_revision(conn, tenant_id)
                conn.execute(
                    """UPDATE unified_runtime_entities SET deleted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP,
                    version=version+1,revision=?,updated_by=?
                    WHERE tenant_id=? AND owner_user_id=? AND entity_type=? AND entity_id=?""",
                    (revision, updated_by, tenant_id, owner_user_id, entity_type, entity_id),
                )
            conn.commit()
        return True

    def changes(
        self,
        *,
        tenant_id: str,
        since_revision: int,
        owner_user_id: str | None = None,
        entity_types: list[str] | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        sql = "SELECT * FROM unified_runtime_entities WHERE tenant_id=? AND revision>?"
        params: list[Any] = [tenant_id, int(since_revision)]
        if owner_user_id is not None:
            sql += " AND owner_user_id=?"
            params.append(owner_user_id)
        if entity_types:
            placeholders = ",".join("?" for _ in entity_types)
            sql += f" AND entity_type IN ({placeholders})"
            params.extend(entity_types)
        sql += " ORDER BY revision ASC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        items = [self._decode(r) for r in rows]
        current = self.current_revision(tenant_id=tenant_id)
        next_revision = max([int(x.get("_revision") or 0) for x in items], default=since_revision)
        return {
            "items": items,
            "since_revision": int(since_revision),
            "next_revision": next_revision,
            "current_revision": current,
            "has_more": bool(items) and next_revision < current and len(items) >= limit,
        }

    def replace(
        self,
        *,
        tenant_id: str,
        entity_type: str,
        items: list[dict[str, Any]],
        owner_user_id: str = "",
        scope_owner_user_id: str | None = None,
        updated_by: str = "",
    ) -> list[dict[str, Any]]:
        """Migration-only owner-scoped reconciliation.

        The v1.4 API no longer exposes ordinary full-collection replacement. This method remains for
        explicit migration/import workflows and *requires* an owner scope (empty string is the
        explicit tenant-shared scope). Missing rows are soft-deleted rather than hard-deleted.
        """
        if scope_owner_user_id is None:
            raise ValueError("replace requires explicit owner scope; tenant-wide implicit replace is forbidden")
        normalized: dict[str, dict[str, Any]] = {}
        for item in items or []:
            entity_id = str(item.get("id") or item.get("entity_id") or "").strip()
            if not entity_id:
                raise ValueError(f"{entity_type} entity missing id")
            clean = dict(item)
            clean["id"] = entity_id
            normalized[entity_id] = clean
        existing = self.list_all(
            tenant_id=tenant_id, entity_type=entity_type,
            owner_user_id=scope_owner_user_id, include_deleted=False,
        )
        existing_ids = {str(x.get("id")) for x in existing}
        for entity_id in existing_ids - set(normalized):
            self.delete(
                tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
                owner_user_id=scope_owner_user_id, updated_by=updated_by,
            )
        for entity_id, payload in normalized.items():
            current = next((x for x in existing if str(x.get("id")) == entity_id), None)
            self.upsert(
                tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
                payload=payload, owner_user_id=owner_user_id,
                expected_version=(int(current.get("_version")) if current else None),
                updated_by=updated_by,
            )
        return self.list_all(
            tenant_id=tenant_id, entity_type=entity_type,
            owner_user_id=scope_owner_user_id,
        )

    def snapshot(
        self,
        *,
        tenant_id: str,
        entity_types: list[str],
        owner_user_id: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            name: self.list_all(
                tenant_id=tenant_id, entity_type=name, owner_user_id=owner_user_id
            )
            for name in entity_types
        }

    def clear_tenant(self, *, tenant_id: str) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM unified_runtime_entities WHERE tenant_id=?", (tenant_id,))
            conn.execute("DELETE FROM unified_runtime_revisions WHERE tenant_id=?", (tenant_id,))
            conn.commit()
        return int(cur.rowcount or 0)
