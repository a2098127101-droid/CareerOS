from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4


class ArtifactStore:
    """Logical artifact + immutable version store.

    Public methods intentionally preserve the v0.6 return shape while adding artifact_id/version_id
    and a single version chain for writer/revision outputs.
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

    @staticmethod
    def _base_kind(kind: str) -> str:
        return kind.removesuffix("_revision")

    def create_version(
        self,
        session_id: str,
        kind: str,
        title: str,
        content: str,
        metadata: dict | None = None,
        evidence_links: list[dict] | None = None,
        *,
        tenant_id: str = "demo-org",
        owner_user_id: str = "",
        source: str | None = None,
        created_by: str = "",
        artifact_id: str | None = None,
    ) -> dict:
        base_kind = self._base_kind(kind)
        clean_title = title.replace(" · 修订版", "").replace(" · 初稿", "")
        source = source or ("revision_agent" if kind.endswith("_revision") else "writer_agent")
        with self._lock, self._connect() as conn:
            if artifact_id:
                row = conn.execute(
                    "SELECT * FROM artifact_series WHERE artifact_id=? AND tenant_id=? AND deleted_at IS NULL",
                    (artifact_id, tenant_id),
                ).fetchone()
            else:
                # Legacy writer/revision agents that do not supply an artifact id continue the
                # historical one-series-per-kind behavior. Workspace callers always supply an id.
                row = conn.execute(
                    "SELECT * FROM artifact_series WHERE session_id=? AND kind=? AND tenant_id=? AND deleted_at IS NULL",
                    (session_id, base_kind, tenant_id),
                ).fetchone()
            if row:
                artifact_id = row["artifact_id"]
            else:
                artifact_id = artifact_id or f"ART-{uuid4().hex[:12].upper()}"
                conn.execute(
                    """INSERT INTO artifact_series(artifact_id,tenant_id,session_id,owner_user_id,kind,title)
                    VALUES(?,?,?,?,?,?)""",
                    (artifact_id, tenant_id, session_id, owner_user_id, base_kind, clean_title),
                )
            maxv = conn.execute(
                "SELECT COALESCE(MAX(version),0) AS v FROM artifact_versions WHERE artifact_id=?", (artifact_id,)
            ).fetchone()
            version = int(maxv["v"]) + 1
            version_id = f"VER-{uuid4().hex[:14].upper()}"
            conn.execute(
                """INSERT INTO artifact_versions(version_id,artifact_id,tenant_id,session_id,version,content,source,created_by,metadata_json,evidence_links_json)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    version_id,
                    artifact_id,
                    tenant_id,
                    session_id,
                    version,
                    content,
                    source,
                    created_by,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    json.dumps(evidence_links or [], ensure_ascii=False),
                ),
            )
            conn.execute(
                """UPDATE artifact_series SET current_version_id=?, tenant_id=?, owner_user_id=CASE WHEN ?<>'' THEN ? ELSE owner_user_id END,
                title=?, version=?, updated_at=CURRENT_TIMESTAMP WHERE artifact_id=?""",
                (version_id, tenant_id, owner_user_id, owner_user_id, clean_title, version, artifact_id),
            )
            conn.commit()
        return self.get_version(version_id)

    def get(self, artifact_id: str, *, tenant_id: str | None = None) -> dict:
        """Return the current version for a logical artifact ID.

        For backwards compatibility, a version_id is also accepted.
        """
        if artifact_id.startswith("VER-"):
            return self.get_version(artifact_id, tenant_id=tenant_id)
        sql = """SELECT s.*,v.* FROM artifact_series s
        JOIN artifact_versions v ON v.version_id=s.current_version_id WHERE s.artifact_id=? AND s.deleted_at IS NULL"""
        params: list[str] = [artifact_id]
        if tenant_id is not None:
            sql += " AND s.tenant_id=?"
            params.append(tenant_id)
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        if not row:
            raise KeyError(artifact_id)
        return self._joined_row(row)

    def get_version(self, version_id: str, *, tenant_id: str | None = None) -> dict:
        sql = """SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.*
        FROM artifact_versions v JOIN artifact_series s ON s.artifact_id=v.artifact_id
        WHERE v.version_id=? AND s.deleted_at IS NULL"""
        params: list[str] = [version_id]
        if tenant_id is not None:
            sql += " AND v.tenant_id=?"
            params.append(tenant_id)
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        if not row:
            raise KeyError(version_id)
        return self._joined_row(row)

    def list_session(
        self,
        session_id: str,
        include_content: bool = False,
        *,
        tenant_id: str | None = None,
        all_versions: bool = True,
    ) -> list[dict]:
        params: list[str] = [session_id]
        tenant_clause = ""
        if tenant_id is not None:
            tenant_clause = " AND s.tenant_id=?"
            params.append(tenant_id)
        if all_versions:
            sql = f"""SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.*
            FROM artifact_series s JOIN artifact_versions v ON v.artifact_id=s.artifact_id
            WHERE s.session_id=? AND s.deleted_at IS NULL{tenant_clause}
            ORDER BY v.created_at DESC,v.version DESC"""
        else:
            sql = f"""SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.*
            FROM artifact_series s JOIN artifact_versions v ON v.version_id=s.current_version_id
            WHERE s.session_id=? AND s.deleted_at IS NULL{tenant_clause}
            ORDER BY s.updated_at DESC"""
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        result = [self._joined_row(row) for row in rows]
        if not include_content:
            for item in result:
                item.pop("content", None)
        return result

    def latest(self, session_id: str, kind: str | None = None, *, tenant_id: str | None = None) -> dict | None:
        sql = """SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.*
        FROM artifact_series s JOIN artifact_versions v ON v.version_id=s.current_version_id
        WHERE s.session_id=? AND s.deleted_at IS NULL"""
        params: list[str] = [session_id]
        if kind:
            sql += " AND s.kind=?"
            params.append(self._base_kind(kind))
        if tenant_id is not None:
            sql += " AND s.tenant_id=?"
            params.append(tenant_id)
        sql += " ORDER BY s.updated_at DESC LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return self._joined_row(row) if row else None



    def create_workspace_version(
        self,
        *,
        session_id: str,
        title: str,
        kind: str,
        content: str,
        evidence_ids: list[str] | None = None,
        tenant_id: str,
        owner_user_id: str,
        created_by: str = "",
        artifact_id: str | None = None,
    ) -> dict:
        links = [{"evidence_id": x} for x in (evidence_ids or []) if x]
        return self.create_version(
            session_id=session_id, kind=kind or "custom", title=title or "Artifact", content=content or "",
            metadata={"workspace_evidence_ids": list(evidence_ids or [])}, evidence_links=links,
            tenant_id=tenant_id, owner_user_id=owner_user_id, source="workspace", created_by=created_by, artifact_id=artifact_id,
        )

    def update_workspace_artifact(
        self,
        artifact_id: str,
        *,
        tenant_id: str,
        owner_user_id: str,
        title: str,
        content: str,
        kind: str | None = None,
        evidence_ids: list[str] | None = None,
        created_by: str = "",
        expected_version: int | None = None,
    ) -> dict:
        current = self.get(artifact_id, tenant_id=tenant_id)
        if owner_user_id and current.get("owner_user_id") not in {"", owner_user_id}:
            raise PermissionError("artifact owner mismatch")
        actual = int(current.get("version") or 1)
        if expected_version is not None and expected_version != actual:
            from .unified_runtime_store import RuntimeVersionConflict
            raise RuntimeVersionConflict(artifact_id, expected_version, actual)
        base_kind = kind or current.get("kind") or "custom"
        return self.create_workspace_version(
            session_id=current["session_id"], title=title or current.get("title") or "Artifact", kind=base_kind,
            content=content, evidence_ids=evidence_ids, tenant_id=tenant_id, owner_user_id=owner_user_id,
            created_by=created_by, artifact_id=artifact_id,
        )

    def delete_artifact(
        self, artifact_id: str, *, tenant_id: str, owner_user_id: str, expected_version: int | None = None
    ) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT v.version,s.owner_user_id FROM artifact_series s JOIN artifact_versions v ON v.version_id=s.current_version_id WHERE s.artifact_id=? AND s.tenant_id=? AND s.deleted_at IS NULL",
                (artifact_id, tenant_id),
            ).fetchone()
            if not row:
                return False
            if owner_user_id and row["owner_user_id"] not in {"", owner_user_id}:
                raise PermissionError("artifact owner mismatch")
            actual = int(row["version"] or 1)
            if expected_version is not None and expected_version != actual:
                from .unified_runtime_store import RuntimeVersionConflict
                raise RuntimeVersionConflict(artifact_id, expected_version, actual)
            conn.execute(
                "UPDATE artifact_series SET deleted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP,version=version+1 WHERE artifact_id=? AND tenant_id=?",
                (artifact_id, tenant_id),
            )
            conn.commit()
        return True

    @staticmethod
    def to_workspace_item(row: dict) -> dict:
        metadata = row.get("metadata") or {}
        evidence_ids = list(metadata.get("workspace_evidence_ids") or [])
        if not evidence_ids:
            evidence_ids = [x.get("evidence_id") for x in (row.get("evidence_links") or []) if x.get("evidence_id")]
        return {
            "id": row.get("artifact_id", ""),
            "title": row.get("title", "Artifact"),
            "type": row.get("kind", "custom"),
            "content": row.get("content", ""),
            "evidenceIds": evidence_ids,
            "version": int(row.get("version") or 1),
            "versionId": row.get("version_id", ""),
            "createdAt": str(row.get("created_at") or ""),
            "updatedAt": str(row.get("created_at") or ""),
            "_version": int(row.get("version") or 1),
        }

    def list_versions(self, artifact_id: str, *, tenant_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.*
                FROM artifact_versions v JOIN artifact_series s ON s.artifact_id=v.artifact_id
                WHERE v.artifact_id=? AND v.tenant_id=? ORDER BY v.version DESC""",
                (artifact_id,tenant_id),
            ).fetchall()
        return [self._joined_row(r) for r in rows]

    def restore_version(self, artifact_id: str, version_id: str, *, tenant_id: str) -> dict:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM artifact_versions WHERE artifact_id=? AND version_id=? AND tenant_id=?",
                (artifact_id, version_id, tenant_id),
            ).fetchone()
            if not row:
                raise KeyError(version_id)
            conn.execute(
                "UPDATE artifact_series SET current_version_id=?,updated_at=CURRENT_TIMESTAMP WHERE artifact_id=? AND tenant_id=?",
                (version_id, artifact_id, tenant_id),
            )
            conn.commit()
        return self.get(artifact_id, tenant_id=tenant_id)

    def diff_versions(self, artifact_id: str, from_version: int, to_version: int, *, tenant_id: str) -> dict:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT version,content,version_id FROM artifact_versions
                WHERE artifact_id=? AND tenant_id=? AND version IN (?,?)""",
                (artifact_id, tenant_id, from_version, to_version),
            ).fetchall()
        byv = {int(r["version"]): dict(r) for r in rows}
        if from_version not in byv or to_version not in byv:
            raise KeyError("version not found")
        import difflib
        diff = "\n".join(difflib.unified_diff(
            byv[from_version]["content"].splitlines(),
            byv[to_version]["content"].splitlines(),
            fromfile=f"V{from_version}",
            tofile=f"V{to_version}",
            lineterm="",
        ))
        return {"artifact_id": artifact_id, "from": from_version, "to": to_version, "diff": diff}

    @staticmethod
    def _joined_row(row: sqlite3.Row) -> dict:
        data = dict(row)
        # sqlite duplicate names resolve to the first occurrence; normalize explicitly.
        if "metadata_json" in data:
            data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
        if "evidence_links_json" in data:
            data["evidence_links"] = json.loads(data.pop("evidence_links_json") or "[]")
        data["logical_artifact_id"] = data.get("artifact_id")
        data["artifact_id"] = data.get("artifact_id")
        data["is_current"] = data.get("version_id") == data.get("current_version_id")
        return data

    def delete_session(self, session_id: str, *, tenant_id: str) -> int:
        with self._lock, self._connect() as conn:
            ids = [r[0] for r in conn.execute("SELECT artifact_id FROM artifact_series WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)).fetchall()]
            count = 0
            for artifact_id in ids:
                count += conn.execute("DELETE FROM artifact_versions WHERE artifact_id=? AND tenant_id=?", (artifact_id, tenant_id)).rowcount
                conn.execute("DELETE FROM artifact_series WHERE artifact_id=? AND tenant_id=?", (artifact_id, tenant_id))
            conn.commit()
            return int(count)
