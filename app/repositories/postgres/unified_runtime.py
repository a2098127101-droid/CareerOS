from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.unified_runtime_store import RuntimeVersionConflict
from ..sqlalchemy_common import SQLAlchemyRepo


class PostgresUnifiedRuntimeRepository(SQLAlchemyRepo):
    """PostgreSQL runtime-state repository.

    Schema creation belongs to Alembic. Runtime code never auto-creates or mutates schema.
    """

    @staticmethod
    def _decode(row: Any) -> dict[str, Any]:
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
    def _next_revision(conn, tenant_id: str) -> int:
        conn.execute(
            text("""INSERT INTO unified_runtime_revisions(tenant_id,revision,updated_at)
            VALUES(:tenant,0,CURRENT_TIMESTAMP) ON CONFLICT(tenant_id) DO NOTHING"""),
            {"tenant": tenant_id},
        )
        row = conn.execute(
            text("""UPDATE unified_runtime_revisions SET revision=revision+1,updated_at=CURRENT_TIMESTAMP
            WHERE tenant_id=:tenant RETURNING revision"""),
            {"tenant": tenant_id},
        ).mappings().first()
        return int(row["revision"])

    def current_revision(self, *, tenant_id: str) -> int:
        row = self.one(
            "SELECT revision FROM unified_runtime_revisions WHERE tenant_id=:tenant",
            {"tenant": tenant_id},
        )
        return int(row["revision"] if row else 0)

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
        sql = "SELECT * FROM unified_runtime_entities WHERE tenant_id=:tenant AND entity_type=:type"
        params: dict[str, Any] = {"tenant": tenant_id, "type": entity_type, "limit": limit, "offset": offset}
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        if owner_user_id is not None:
            sql += " AND owner_user_id=:owner"
            params["owner"] = owner_user_id
        sql += " ORDER BY revision ASC,owner_user_id ASC,entity_id ASC LIMIT :limit OFFSET :offset"
        return [self._decode(r) for r in self.all(sql, params)]

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
                include_deleted=include_deleted,
                limit=page_size,
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
        sql = "SELECT * FROM unified_runtime_entities WHERE tenant_id=:tenant AND entity_type=:type AND entity_id=:id"
        params: dict[str, Any] = {"tenant": tenant_id, "type": entity_type, "id": entity_id}
        if owner_user_id is not None:
            sql += " AND owner_user_id=:owner"
            params["owner"] = owner_user_id
        if not include_deleted:
            sql += " AND deleted_at IS NULL"
        rows = self.all(sql, params)
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
        with self.engine.begin() as conn:
            row = conn.execute(
                text("""SELECT version FROM unified_runtime_entities
                WHERE tenant_id=:tenant AND owner_user_id=:owner AND entity_type=:type AND entity_id=:id
                FOR UPDATE"""),
                {"tenant": tenant_id, "owner": owner_user_id, "type": entity_type, "id": entity_id},
            ).mappings().first()
            actual = int(row["version"]) if row else None
            if expected_version is not None and actual != expected_version:
                raise RuntimeVersionConflict(entity_id, expected_version, actual)
            revision = self._next_revision(conn, tenant_id)
            if row:
                version = actual + 1
                conn.execute(
                    text("""UPDATE unified_runtime_entities SET payload_json=:payload,version=:version,revision=:revision,
                    updated_by=:updated_by,deleted_at=NULL,updated_at=CURRENT_TIMESTAMP
                    WHERE tenant_id=:tenant AND owner_user_id=:owner AND entity_type=:type AND entity_id=:id"""),
                    {"payload": raw, "version": version, "revision": revision, "updated_by": updated_by,
                     "tenant": tenant_id, "owner": owner_user_id, "type": entity_type, "id": entity_id},
                )
            else:
                conn.execute(
                    text("""INSERT INTO unified_runtime_entities
                    (tenant_id,owner_user_id,entity_type,entity_id,payload_json,version,revision,updated_by,deleted_at,created_at,updated_at)
                    VALUES(:tenant,:owner,:type,:id,:payload,1,:revision,:updated_by,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""),
                    {"tenant": tenant_id, "owner": owner_user_id, "type": entity_type, "id": entity_id,
                     "payload": raw, "revision": revision, "updated_by": updated_by},
                )
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
        with self.engine.begin() as conn:
            row = conn.execute(
                text("""SELECT version FROM unified_runtime_entities
                WHERE tenant_id=:tenant AND owner_user_id=:owner AND entity_type=:type AND entity_id=:id FOR UPDATE"""),
                {"tenant": tenant_id, "owner": owner_user_id, "type": entity_type, "id": entity_id},
            ).mappings().first()
            if not row:
                return False
            actual = int(row["version"])
            if expected_version is not None and actual != expected_version:
                raise RuntimeVersionConflict(entity_id, expected_version, actual)
            revision = self._next_revision(conn, tenant_id)
            if hard:
                conn.execute(
                    text("DELETE FROM unified_runtime_entities WHERE tenant_id=:tenant AND owner_user_id=:owner AND entity_type=:type AND entity_id=:id"),
                    {"tenant": tenant_id, "owner": owner_user_id, "type": entity_type, "id": entity_id},
                )
            else:
                conn.execute(
                    text("""UPDATE unified_runtime_entities SET deleted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP,
                    version=version+1,revision=:revision,updated_by=:updated_by
                    WHERE tenant_id=:tenant AND owner_user_id=:owner AND entity_type=:type AND entity_id=:id"""),
                    {"revision": revision, "updated_by": updated_by, "tenant": tenant_id,
                     "owner": owner_user_id, "type": entity_type, "id": entity_id},
                )
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
        sql = "SELECT * FROM unified_runtime_entities WHERE tenant_id=:tenant AND revision>:since"
        params: dict[str, Any] = {"tenant": tenant_id, "since": int(since_revision), "limit": limit}
        if owner_user_id is not None:
            sql += " AND owner_user_id=:owner"
            params["owner"] = owner_user_id
        if entity_types:
            names = []
            for idx, value in enumerate(entity_types):
                key = f"type_{idx}"; names.append(f":{key}"); params[key] = value
            sql += " AND entity_type IN (" + ",".join(names) + ")"
        sql += " ORDER BY revision ASC LIMIT :limit"
        items = [self._decode(r) for r in self.all(sql, params)]
        current = self.current_revision(tenant_id=tenant_id)
        next_revision = max([int(x.get("_revision") or 0) for x in items], default=since_revision)
        return {"items": items, "since_revision": int(since_revision), "next_revision": next_revision,
                "current_revision": current, "has_more": bool(items) and next_revision < current and len(items) >= limit}

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
        if scope_owner_user_id is None:
            raise ValueError("replace requires explicit owner scope; tenant-wide implicit replace is forbidden")
        normalized: dict[str, dict[str, Any]] = {}
        for item in items or []:
            entity_id = str(item.get("id") or item.get("entity_id") or "").strip()
            if not entity_id:
                raise ValueError(f"{entity_type} entity missing id")
            clean = dict(item); clean["id"] = entity_id; normalized[entity_id] = clean
        existing = self.list_all(tenant_id=tenant_id, entity_type=entity_type, owner_user_id=scope_owner_user_id)
        existing_by_id = {str(x.get("id")): x for x in existing}
        for entity_id in set(existing_by_id) - set(normalized):
            self.delete(tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
                        owner_user_id=scope_owner_user_id, updated_by=updated_by)
        for entity_id, payload in normalized.items():
            current = existing_by_id.get(entity_id)
            self.upsert(tenant_id=tenant_id, entity_type=entity_type, entity_id=entity_id,
                        payload=payload, owner_user_id=owner_user_id,
                        expected_version=(int(current.get("_version")) if current else None), updated_by=updated_by)
        return self.list_all(tenant_id=tenant_id, entity_type=entity_type, owner_user_id=scope_owner_user_id)

    def snapshot(self, *, tenant_id: str, entity_types: list[str], owner_user_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
        return {name: self.list_all(tenant_id=tenant_id, entity_type=name, owner_user_id=owner_user_id) for name in entity_types}

    def clear_tenant(self, *, tenant_id: str) -> int:
        with self.engine.begin() as conn:
            result = conn.execute(text("DELETE FROM unified_runtime_entities WHERE tenant_id=:tenant"), {"tenant": tenant_id})
            conn.execute(text("DELETE FROM unified_runtime_revisions WHERE tenant_id=:tenant"), {"tenant": tenant_id})
            return int(result.rowcount or 0)
