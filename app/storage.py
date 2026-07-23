from __future__ import annotations

import hashlib
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


class StorageError(RuntimeError):
    pass


@dataclass
class StoredObject:
    object_id: str
    provider: str
    key: str
    filename: str
    size_bytes: int
    sha256: str
    content_type: str


def sanitize_filename(name: str) -> str:
    base = Path(name or "upload").name
    base = re.sub(r"[^\w.\-()\u4e00-\u9fff]+", "_", base, flags=re.UNICODE).strip("._") or "upload"
    return base[:180]


class LocalStorageAdapter:
    def __init__(self, root: str = "data/uploads"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        root = self.root.resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise StorageError("invalid storage key") from exc
        return candidate

    def put(self, *, tenant_id: str, owner_id: str, filename: str, content: bytes, content_type: str = "") -> StoredObject:
        safe = sanitize_filename(filename)
        object_id = f"OBJ-{uuid4().hex[:18].upper()}"
        shard = re.sub(r"[^a-zA-Z0-9_-]", "_", tenant_id or "global")
        owner = re.sub(r"[^a-zA-Z0-9_-]", "_", owner_id or "anonymous")
        rel = Path(shard) / owner / f"{object_id}_{safe}"
        path = self._resolve(str(rel))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        return StoredObject(
            object_id=object_id,
            provider="local",
            key=str(rel).replace("\\", "/"),
            filename=safe,
            size_bytes=len(content),
            sha256=digest,
            content_type=content_type or mimetypes.guess_type(safe)[0] or "application/octet-stream",
        )

    def get_path(self, key: str) -> Path:
        path = self._resolve(key)
        if not path.is_file():
            raise StorageError("object not found")
        return path

    def get(self, key: str) -> bytes:
        return self.get_path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._resolve(key)
        if path.exists():
            path.unlink()


class S3CompatibleStorageAdapter:
    def __init__(self, *, endpoint: str, bucket: str, access_key: str, secret_key: str, region: str = "auto", public_endpoint: str = ""):
        try:
            import boto3  # type: ignore
        except Exception as exc:
            raise StorageError("boto3 is required for STORAGE_PROVIDER=s3") from exc
        if not all([bucket, access_key, secret_key]):
            raise StorageError("S3 bucket/access key/secret key are required")
        self.bucket = bucket
        common = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": region,
        }
        self.client = boto3.client("s3", endpoint_url=endpoint or None, **common)
        # Private/internal endpoints (for example Docker DNS `minio:9000`) are often not reachable by
        # a user's browser. A separate signing client lets presigned URLs use a public endpoint while
        # all storage CRUD continues through the internal endpoint. Signing does not contact the endpoint.
        self.signing_client = boto3.client("s3", endpoint_url=(public_endpoint or endpoint or None), **common)

    def put(self, *, tenant_id: str, owner_id: str, filename: str, content: bytes, content_type: str = "") -> StoredObject:
        safe = sanitize_filename(filename)
        object_id = f"OBJ-{uuid4().hex[:18].upper()}"
        key = f"{tenant_id or 'global'}/{owner_id or 'anonymous'}/{object_id}_{safe}"
        ctype = content_type or mimetypes.guess_type(safe)[0] or "application/octet-stream"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=ctype)
        return StoredObject(
            object_id=object_id,
            provider="s3",
            key=key,
            filename=safe,
            size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
            content_type=ctype,
        )

    def get(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def presigned_get_url(self, key: str, *, expires_seconds: int = 900) -> str:
        return self.signing_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=max(30, int(expires_seconds)),
        )


class StorageRegistry:
    def __init__(self, db_path: str):
        import sqlite3
        self.sqlite3 = sqlite3
        self.db_path = Path(db_path)
        from .migrations import run_migrations
        run_migrations(str(self.db_path))

    def record(self, *, stored: StoredObject, tenant_id: str, owner_user_id: str = "", session_id: str = "", scan_status: str = "unknown") -> dict:
        with self.sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO stored_objects(
                object_id,tenant_id,owner_user_id,session_id,provider,object_key,filename,content_type,size_bytes,sha256,status,scan_status,deleted_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?, 'active', ?, NULL)""",
                (
                    stored.object_id, tenant_id, owner_user_id, session_id, stored.provider, stored.key,
                    stored.filename, stored.content_type, stored.size_bytes, stored.sha256, scan_status,
                ),
            )
            conn.commit()
        return self.get(stored.object_id, tenant_id=tenant_id) or {}

    def get(self, object_id: str, *, tenant_id: str) -> dict | None:
        with self.sqlite3.connect(self.db_path) as conn:
            conn.row_factory = self.sqlite3.Row
            row = conn.execute(
                "SELECT * FROM stored_objects WHERE object_id=? AND tenant_id=? AND COALESCE(status,'active')!='deleted'",
                (object_id, tenant_id),
            ).fetchone()
        return dict(row) if row else None

    def list(self, *, tenant_id: str, owner_user_id: str = "", limit: int = 100) -> list[dict]:
        sql = "SELECT * FROM stored_objects WHERE tenant_id=? AND COALESCE(status,'active')!='deleted'"
        params: list[object] = [tenant_id]
        if owner_user_id:
            sql += " AND owner_user_id=?"
            params.append(owner_user_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(int(limit), 500)))
        with self.sqlite3.connect(self.db_path) as conn:
            conn.row_factory = self.sqlite3.Row
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def mark_deleted(self, object_id: str, *, tenant_id: str) -> bool:
        with self.sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE stored_objects SET status='deleted', deleted_at=CURRENT_TIMESTAMP WHERE object_id=? AND tenant_id=? AND COALESCE(status,'active')!='deleted'",
                (object_id, tenant_id),
            )
            conn.commit()
            return bool(cur.rowcount)

    def count(self, *, tenant_id: str, owner_user_id: str = "") -> int:
        sql = "SELECT COUNT(*) FROM stored_objects WHERE tenant_id=? AND COALESCE(status,'active')!='deleted'"
        params: list[object] = [tenant_id]
        if owner_user_id:
            sql += " AND owner_user_id=?"
            params.append(owner_user_id)
        with self.sqlite3.connect(self.db_path) as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        return int(row[0] if row else 0)
