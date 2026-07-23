from __future__ import annotations

import re
from uuid import uuid4

from sqlalchemy.engine import Engine

from ...evidence_store import is_evidence_candidate
from ..sqlalchemy_common import SQLAlchemyRepo


class PostgresEvidenceRepository(SQLAlchemyRepo):
    def __init__(self, engine: Engine): super().__init__(engine)

    def add(self,session_id:str,source_type:str,source_label:str,content:str,verified:bool=False,*,tenant_id:str="demo-org",owner_user_id:str="")->dict:
        evidence_id=f"EVID-{uuid4().hex[:12].upper()}"
        self.execute("""INSERT INTO evidence_items(evidence_id,session_id,tenant_id,owner_user_id,source_type,source_label,content,verified) VALUES(:id,:session,:tenant,:owner,:stype,:label,:content,:verified)""",{"id":evidence_id,"session":session_id,"tenant":tenant_id,"owner":owner_user_id,"stype":source_type,"label":source_label,"content":content.strip(),"verified":1 if verified else 0})
        return self.get(evidence_id,tenant_id=tenant_id)

    def add_chat_candidate(self,session_id:str,content:str,*,tenant_id:str="demo-org",owner_user_id:str="",source_label:str="用户对话"):
        if not is_evidence_candidate(content):return None
        return self.add(session_id,"student_input",source_label,content,False,tenant_id=tenant_id,owner_user_id=owner_user_id)

    def get(self,evidence_id:str,*,tenant_id:str|None=None)->dict:
        sql="SELECT * FROM evidence_items WHERE evidence_id=:id";params={"id":evidence_id}
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        row=self.one(sql,params)
        if not row:raise KeyError(evidence_id)
        d=dict(row);d["verified"]=bool(d.get("verified"));return d

    def list_session(self,session_id:str,limit:int=100,*,tenant_id:str|None=None)->list[dict]:
        sql="SELECT * FROM evidence_items WHERE session_id=:session";params={"session":session_id,"limit":limit}
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        sql+=" ORDER BY created_at DESC LIMIT :limit";out=[]
        for r in self.all(sql,params):d=dict(r);d["verified"]=bool(d.get("verified"));out.append(d)
        return out

    def build_context(self,session_id:str,max_chars:int=12000,*,tenant_id:str|None=None)->str:
        items=list(reversed(self.list_session(session_id,100,tenant_id=tenant_id)));parts=[];used=0
        for x in items:
            line=f"[{x['evidence_id']}] {x['source_label']}: {x['content']}"
            if used+len(line)>max_chars:break
            parts.append(line);used+=len(line)+1
        return "\n".join(parts)

    @staticmethod
    def _tokens(text:str)->set[str]:
        return set(re.findall(r"[\w\u4e00-\u9fff]{2,}",text.lower()))

    def link_text(self,session_id:str,text:str,max_links:int=30,*,tenant_id:str|None=None)->list[dict]:
        target=self._tokens(text);links=[]
        for e in self.list_session(session_id,100,tenant_id=tenant_id):
            toks=self._tokens(e["content"]);score=len(target & toks)/max(1,len(toks))
            if score>0.08:links.append({"evidence_id":e["evidence_id"],"source_label":e["source_label"],"confidence":round(min(1.0,score),3)})
        return sorted(links,key=lambda x:x["confidence"],reverse=True)[:max_links]

    def delete_session(self, session_id: str, *, tenant_id: str) -> int:
        return self.execute("DELETE FROM evidence_items WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id})
