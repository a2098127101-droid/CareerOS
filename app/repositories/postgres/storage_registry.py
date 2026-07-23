from __future__ import annotations
from sqlalchemy.engine import Engine
from ...storage import StoredObject
from ..sqlalchemy_common import SQLAlchemyRepo


class PostgresStorageRegistry(SQLAlchemyRepo):
    def __init__(self, engine: Engine):
        super().__init__(engine)

    def record(self, *, stored: StoredObject, tenant_id: str, owner_user_id: str = '', session_id: str = '', scan_status: str = 'unknown') -> dict:
        params = {
            'id': stored.object_id, 'tenant': tenant_id, 'owner': owner_user_id, 'session': session_id,
            'provider': stored.provider, 'key': stored.key, 'filename': stored.filename,
            'ctype': stored.content_type, 'size': stored.size_bytes, 'sha': stored.sha256, 'scan': scan_status,
        }
        if self.one('SELECT 1 FROM stored_objects WHERE object_id=:id', {'id': stored.object_id}):
            self.execute(
                """UPDATE stored_objects SET tenant_id=:tenant,owner_user_id=:owner,session_id=:session,
                provider=:provider,object_key=:key,filename=:filename,content_type=:ctype,size_bytes=:size,sha256=:sha,
                status='active',scan_status=:scan,deleted_at=NULL WHERE object_id=:id""", params,
            )
        else:
            self.execute(
                """INSERT INTO stored_objects(object_id,tenant_id,owner_user_id,session_id,provider,object_key,filename,content_type,size_bytes,sha256,status,scan_status)
                VALUES(:id,:tenant,:owner,:session,:provider,:key,:filename,:ctype,:size,:sha,'active',:scan)""", params,
            )
        return self.get(stored.object_id, tenant_id=tenant_id) or {}

    def get(self, object_id: str, *, tenant_id: str) -> dict | None:
        return self.one(
            "SELECT * FROM stored_objects WHERE object_id=:id AND tenant_id=:tenant AND COALESCE(status,'active')!='deleted'",
            {'id': object_id, 'tenant': tenant_id},
        )

    def list(self, *, tenant_id: str, owner_user_id: str = '', limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        if owner_user_id:
            return self.all(
                """SELECT * FROM stored_objects WHERE tenant_id=:tenant AND owner_user_id=:owner
                AND COALESCE(status,'active')!='deleted' ORDER BY created_at DESC LIMIT :limit""",
                {'tenant': tenant_id, 'owner': owner_user_id, 'limit': limit},
            )
        return self.all(
            """SELECT * FROM stored_objects WHERE tenant_id=:tenant AND COALESCE(status,'active')!='deleted'
            ORDER BY created_at DESC LIMIT :limit""",
            {'tenant': tenant_id, 'limit': limit},
        )

    def mark_deleted(self, object_id: str, *, tenant_id: str) -> bool:
        result = self.execute(
            """UPDATE stored_objects SET status='deleted',deleted_at=CURRENT_TIMESTAMP
            WHERE object_id=:id AND tenant_id=:tenant AND COALESCE(status,'active')!='deleted'""",
            {'id': object_id, 'tenant': tenant_id},
        )
        return bool(result)

    def count(self, *, tenant_id: str, owner_user_id: str = "") -> int:
        sql = "SELECT COUNT(*) AS c FROM stored_objects WHERE tenant_id=:tenant AND COALESCE(status,'active')!='deleted'"
        params = {"tenant": tenant_id}
        if owner_user_id:
            sql += " AND owner_user_id=:owner"
            params["owner"] = owner_user_id
        row = self.one(sql, params)
        return int(row["c"] if row else 0)
