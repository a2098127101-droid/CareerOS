from __future__ import annotations

import difflib
import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..sqlalchemy_common import SQLAlchemyRepo


class PostgresArtifactRepository(SQLAlchemyRepo):
    def __init__(self, engine: Engine):
        super().__init__(engine)

    @staticmethod
    def _base_kind(kind: str) -> str:
        return kind.removesuffix("_revision")

    @staticmethod
    def _joined_row(row) -> dict:
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json", "{}") or "{}")
        data["evidence_links"] = json.loads(data.pop("evidence_links_json", "[]") or "[]")
        data["is_current"] = data.get("version_id") == data.get("current_version_id")
        data["kind"] = data.get("kind", "")
        return data

    def create_version(self, session_id: str, kind: str, title: str, content: str, metadata: dict | None=None, evidence_links: list[dict] | None=None, *, tenant_id: str="demo-org", owner_user_id: str="", source: str | None=None, created_by: str="") -> dict:
        base_kind=self._base_kind(kind)
        clean_title=title.replace(" · 修订版","").replace(" · 初稿","")
        source=source or ("revision_agent" if kind.endswith("_revision") else "writer_agent")
        with self.engine.begin() as conn:
            row=conn.execute(text("SELECT artifact_id FROM artifact_series WHERE session_id=:session AND kind=:kind AND tenant_id=:tenant"),{"session":session_id,"kind":base_kind,"tenant":tenant_id}).mappings().first()
            if row: artifact_id=row["artifact_id"]
            else:
                artifact_id=f"ART-{uuid4().hex[:12].upper()}"
                conn.execute(text("""INSERT INTO artifact_series(artifact_id,tenant_id,session_id,owner_user_id,kind,title) VALUES(:id,:tenant,:session,:owner,:kind,:title)"""),{"id":artifact_id,"tenant":tenant_id,"session":session_id,"owner":owner_user_id,"kind":base_kind,"title":clean_title})
            maxv=conn.execute(text("SELECT COALESCE(MAX(version),0) AS v FROM artifact_versions WHERE artifact_id=:id AND tenant_id=:tenant"),{"id":artifact_id,"tenant":tenant_id}).mappings().first()
            version=int(maxv["v"] or 0)+1; version_id=f"VER-{uuid4().hex[:14].upper()}"
            conn.execute(text("""INSERT INTO artifact_versions(version_id,artifact_id,tenant_id,session_id,version,content,source,created_by,metadata_json,evidence_links_json) VALUES(:vid,:aid,:tenant,:session,:version,:content,:source,:created_by,:metadata,:evidence)"""),{"vid":version_id,"aid":artifact_id,"tenant":tenant_id,"session":session_id,"version":version,"content":content,"source":source,"created_by":created_by,"metadata":json.dumps(metadata or {},ensure_ascii=False),"evidence":json.dumps(evidence_links or [],ensure_ascii=False)})
            conn.execute(text("""UPDATE artifact_series SET current_version_id=:vid,tenant_id=:tenant,owner_user_id=CASE WHEN :owner<>'' THEN :owner ELSE owner_user_id END,title=:title,updated_at=CURRENT_TIMESTAMP WHERE artifact_id=:aid AND tenant_id=:tenant"""),{"vid":version_id,"tenant":tenant_id,"owner":owner_user_id,"title":clean_title,"aid":artifact_id})
        return self.get_version(version_id,tenant_id=tenant_id)

    def get(self, artifact_id: str, *, tenant_id: str | None=None) -> dict:
        if artifact_id.startswith("VER-"): return self.get_version(artifact_id,tenant_id=tenant_id)
        sql="""SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.* FROM artifact_series s JOIN artifact_versions v ON v.version_id=s.current_version_id WHERE s.artifact_id=:id"""; params={"id":artifact_id}
        if tenant_id is not None: sql+=" AND s.tenant_id=:tenant"; params["tenant"]=tenant_id
        row=self.one(sql,params)
        if not row: raise KeyError(artifact_id)
        return self._joined_row(row)

    def get_version(self,version_id:str,*,tenant_id:str|None=None)->dict:
        sql="""SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.* FROM artifact_versions v JOIN artifact_series s ON s.artifact_id=v.artifact_id WHERE v.version_id=:id""";params={"id":version_id}
        if tenant_id is not None:sql+=" AND v.tenant_id=:tenant";params["tenant"]=tenant_id
        row=self.one(sql,params)
        if not row:raise KeyError(version_id)
        return self._joined_row(row)

    def list_session(self,session_id:str,include_content:bool=False,*,tenant_id:str|None=None,all_versions:bool=True)->list[dict]:
        params={"session":session_id}; tenant_clause=""
        if tenant_id is not None:tenant_clause=" AND s.tenant_id=:tenant";params["tenant"]=tenant_id
        if all_versions:sql=f"""SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.* FROM artifact_series s JOIN artifact_versions v ON v.artifact_id=s.artifact_id WHERE s.session_id=:session{tenant_clause} ORDER BY v.created_at DESC,v.version DESC"""
        else:sql=f"""SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.* FROM artifact_series s JOIN artifact_versions v ON v.version_id=s.current_version_id WHERE s.session_id=:session{tenant_clause} ORDER BY s.updated_at DESC"""
        result=[self._joined_row(r) for r in self.all(sql,params)]
        if not include_content:
            for item in result:item.pop("content",None)
        return result

    def latest(self,session_id:str,kind:str|None=None,*,tenant_id:str|None=None)->dict|None:
        sql="""SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.* FROM artifact_series s JOIN artifact_versions v ON v.version_id=s.current_version_id WHERE s.session_id=:session""";params={"session":session_id}
        if kind:sql+=" AND s.kind=:kind";params["kind"]=self._base_kind(kind)
        if tenant_id is not None:sql+=" AND s.tenant_id=:tenant";params["tenant"]=tenant_id
        sql+=" ORDER BY s.updated_at DESC LIMIT 1";row=self.one(sql,params);return self._joined_row(row) if row else None

    def list_versions(self,artifact_id:str,*,tenant_id:str)->list[dict]:
        return [self._joined_row(r) for r in self.all("""SELECT s.title,s.kind,s.owner_user_id,s.current_version_id,v.* FROM artifact_versions v JOIN artifact_series s ON s.artifact_id=v.artifact_id WHERE v.artifact_id=:aid AND v.tenant_id=:tenant ORDER BY v.version DESC""",{"aid":artifact_id,"tenant":tenant_id})]

    def restore_version(self,artifact_id:str,version_id:str,*,tenant_id:str)->dict:
        with self.engine.begin() as conn:
            row=conn.execute(text("SELECT 1 FROM artifact_versions WHERE artifact_id=:aid AND version_id=:vid AND tenant_id=:tenant"),{"aid":artifact_id,"vid":version_id,"tenant":tenant_id}).first()
            if not row:raise KeyError(version_id)
            conn.execute(text("UPDATE artifact_series SET current_version_id=:vid,updated_at=CURRENT_TIMESTAMP WHERE artifact_id=:aid AND tenant_id=:tenant"),{"vid":version_id,"aid":artifact_id,"tenant":tenant_id})
        return self.get(artifact_id,tenant_id=tenant_id)

    def diff_versions(self,artifact_id:str,from_version:int,to_version:int,*,tenant_id:str)->dict:
        rows=self.all("""SELECT version,content FROM artifact_versions WHERE artifact_id=:aid AND tenant_id=:tenant AND version IN (:a,:b) ORDER BY version""",{"aid":artifact_id,"tenant":tenant_id,"a":from_version,"b":to_version})
        by={int(r["version"]):r["content"] for r in rows}
        if from_version not in by or to_version not in by:raise KeyError("version not found")
        diff="\n".join(difflib.unified_diff(by[from_version].splitlines(),by[to_version].splitlines(),fromfile=f"V{from_version}",tofile=f"V{to_version}",lineterm=""))
        return {"artifact_id":artifact_id,"from_version":from_version,"to_version":to_version,"diff":diff}

    def delete_session(self, session_id: str, *, tenant_id: str) -> int:
        rows = self.all("SELECT artifact_id FROM artifact_series WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id})
        count = 0
        for row in rows:
            count += self.execute("DELETE FROM artifact_versions WHERE artifact_id=:id AND tenant_id=:tenant", {"id": row["artifact_id"], "tenant": tenant_id})
            self.execute("DELETE FROM artifact_series WHERE artifact_id=:id AND tenant_id=:tenant", {"id": row["artifact_id"], "tenant": tenant_id})
        return count
