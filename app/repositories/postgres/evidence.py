from __future__ import annotations

import json
import re
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ...evidence_store import is_evidence_candidate
from ...unified_runtime_store import RuntimeVersionConflict
from ..sqlalchemy_common import SQLAlchemyRepo


class PostgresEvidenceRepository(SQLAlchemyRepo):
    def __init__(self, engine: Engine):
        super().__init__(engine)

    def add(self, session_id: str, source_type: str, source_label: str, content: str, verified: bool=False, *, tenant_id: str="demo-org", owner_user_id: str="") -> dict:
        evidence_id=f"EVID-{uuid4().hex[:12].upper()}"
        self.execute("""INSERT INTO evidence_items(evidence_id,session_id,tenant_id,owner_user_id,source_type,source_label,content,verified,metadata_json,version,updated_at,deleted_at,verification_status,verification_confidence)
        VALUES(:id,:session,:tenant,:owner,:stype,:label,:content,:verified,'{}',1,CURRENT_TIMESTAMP,NULL,:vstatus,:vconfidence)""",
        {"id":evidence_id,"session":session_id,"tenant":tenant_id,"owner":owner_user_id,"stype":source_type,"label":source_label,"content":content.strip(),"verified":1 if verified else 0,"vstatus":"VERIFIED" if verified else ("EXTRACTED" if source_type in {"file","attachment","parser"} else "SELF_REPORTED"),"vconfidence":1.0 if verified else 0.0})
        return self.get(evidence_id,tenant_id=tenant_id)

    def add_structured(self, session_id: str, *, title: str, action: str, proof: str="", capabilities: list[str]|None=None, verified: bool=False,
                       tenant_id: str="demo-org", owner_user_id: str="", evidence_id: str|None=None) -> dict:
        evidence_id=evidence_id or f"EVID-{uuid4().hex[:12].upper()}"
        metadata={"action":action,"proof":proof or "","capabilities":list(capabilities or [])}
        self.execute("""INSERT INTO evidence_items(evidence_id,session_id,tenant_id,owner_user_id,source_type,source_label,content,verified,metadata_json,version,updated_at,deleted_at,verification_status,verification_confidence)
        VALUES(:id,:session,:tenant,:owner,'structured',:label,:content,:verified,:metadata,1,CURRENT_TIMESTAMP,NULL,:vstatus,:vconfidence)""",
        {"id":evidence_id,"session":session_id,"tenant":tenant_id,"owner":owner_user_id,"label":title[:160],"content":action[:120000],"verified":1 if verified else 0,"metadata":json.dumps(metadata,ensure_ascii=False),"vstatus":"VERIFIED" if verified else "SELF_REPORTED","vconfidence":1.0 if verified else 0.0})
        return self.get(evidence_id,tenant_id=tenant_id)

    def add_chat_candidate(self,session_id:str,content:str,*,tenant_id:str="demo-org",owner_user_id:str="",source_label:str="用户对话"):
        if not is_evidence_candidate(content):return None
        return self.add(session_id,"student_input",source_label,content,False,tenant_id=tenant_id,owner_user_id=owner_user_id)

    def get(self,evidence_id:str,*,tenant_id:str|None=None)->dict:
        sql="SELECT * FROM evidence_items WHERE evidence_id=:id AND deleted_at IS NULL";params={"id":evidence_id}
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        row=self.one(sql,params)
        if not row:raise KeyError(evidence_id)
        d=dict(row);d["verified"]=bool(d.get("verified"));return d

    def list_session(self,session_id:str,limit:int=100,*,tenant_id:str|None=None)->list[dict]:
        sql="SELECT * FROM evidence_items WHERE session_id=:session AND deleted_at IS NULL";params={"session":session_id,"limit":limit}
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        sql+=" ORDER BY created_at DESC LIMIT :limit";out=[]
        for r in self.all(sql,params):d=dict(r);d["verified"]=bool(d.get("verified"));out.append(d)
        return out

    def update_structured(self,evidence_id:str,*,tenant_id:str,owner_user_id:str,title:str|None=None,action:str|None=None,proof:str|None=None,
                          capabilities:list[str]|None=None,verified:bool|None=None,expected_version:int|None=None)->dict:
        with self.engine.begin() as conn:
            row=conn.execute(text("SELECT * FROM evidence_items WHERE evidence_id=:id AND tenant_id=:tenant AND owner_user_id=:owner AND deleted_at IS NULL FOR UPDATE"),
                             {"id":evidence_id,"tenant":tenant_id,"owner":owner_user_id}).mappings().first()
            if not row:raise KeyError(evidence_id)
            current=dict(row);actual=int(current.get("version") or 1)
            if expected_version is not None and expected_version!=actual:raise RuntimeVersionConflict(evidence_id,expected_version,actual)
            try:meta=json.loads(current.get("metadata_json") or "{}")
            except Exception:meta={}
            old_meta=dict(meta)
            next_title=(title if title is not None else current.get("source_label") or "Evidence")[:160]
            next_action=(action if action is not None else meta.get("action") or current.get("content") or "").strip()
            meta["action"]=next_action
            if proof is not None:meta["proof"]=proof
            if capabilities is not None:meta["capabilities"]=list(capabilities)
            current_status=str(current.get("verification_status") or ("VERIFIED" if current.get("verified") else "SELF_REPORTED"))
            material_changed=(next_title!=(current.get("source_label") or "") or next_action!=(current.get("content") or "") or meta.get("proof","")!=old_meta.get("proof","") or list(meta.get("capabilities") or [])!=list(old_meta.get("capabilities") or []))
            invalidated=material_changed and current_status in {"VERIFIED","PARTIALLY_VERIFIED","REJECTED","CONTRADICTED"}
            next_status=("EXTRACTED" if str(current.get("source_type") or "") in {"file","attachment","parser"} else "SELF_REPORTED") if invalidated else current_status
            next_verified=1 if next_status=="VERIFIED" else 0
            conn.execute(text("""UPDATE evidence_items SET source_label=:label,content=:content,verified=:verified,metadata_json=:metadata,
                verification_status=:status,verification_confidence=:confidence,verified_by=:verified_by,verified_at=:verified_at,
                version=version+1,updated_at=CURRENT_TIMESTAMP WHERE evidence_id=:id AND tenant_id=:tenant AND owner_user_id=:owner"""),
                {"label":next_title,"content":next_action[:120000],"verified":next_verified,"metadata":json.dumps(meta,ensure_ascii=False),
                 "status":next_status,"confidence":0.0 if invalidated else float(current.get("verification_confidence") or 0),
                 "verified_by":"" if invalidated else str(current.get("verified_by") or ""),"verified_at":None if invalidated else current.get("verified_at"),
                 "id":evidence_id,"tenant":tenant_id,"owner":owner_user_id})
            if invalidated:
                conn.execute(text("""INSERT INTO evidence_item_verification_history
                    (history_id,tenant_id,session_id,evidence_id,previous_status,new_status,decision,confidence,method,reason,actor_user_id)
                    VALUES(:id,:tenant,:session,:evidence,:previous,:new,'invalidated',0,'material_edit','Material edit invalidated previous verification',:actor)"""),
                    {"id":f"EVH-{uuid4().hex[:18].upper()}","tenant":tenant_id,"session":current.get("session_id") or "","evidence":evidence_id,"previous":current_status,"new":next_status,"actor":owner_user_id})
        return self.get(evidence_id,tenant_id=tenant_id)

    def delete_item(self,evidence_id:str,*,tenant_id:str,owner_user_id:str,expected_version:int|None=None)->bool:
        with self.engine.begin() as conn:
            row=conn.execute(text("SELECT version FROM evidence_items WHERE evidence_id=:id AND tenant_id=:tenant AND owner_user_id=:owner AND deleted_at IS NULL FOR UPDATE"),
                             {"id":evidence_id,"tenant":tenant_id,"owner":owner_user_id}).mappings().first()
            if not row:return False
            actual=int(row.get("version") or 1)
            if expected_version is not None and expected_version!=actual:raise RuntimeVersionConflict(evidence_id,expected_version,actual)
            conn.execute(text("UPDATE evidence_items SET deleted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP,version=version+1 WHERE evidence_id=:id AND tenant_id=:tenant AND owner_user_id=:owner"),
                         {"id":evidence_id,"tenant":tenant_id,"owner":owner_user_id})
        return True

    @staticmethod
    def to_workspace_item(row:dict)->dict:
        try:meta=json.loads(row.get("metadata_json") or "{}")
        except Exception:meta={}
        status=str(row.get("verification_status") or ("VERIFIED" if row.get("verified") else "SELF_REPORTED"))
        return {"id":row.get("evidence_id",""),"title":row.get("source_label","Evidence"),"action":meta.get("action") or row.get("content",""),
                "proof":meta.get("proof",""),"capabilities":list(meta.get("capabilities") or []),"verified":status=="VERIFIED",
                "verificationStatus":status,"verificationConfidence":float(row.get("verification_confidence") or 0),
                "verifiedBy":str(row.get("verified_by") or ""),"verifiedAt":str(row.get("verified_at") or ""),
                "createdAt":str(row.get("created_at") or ""),"updatedAt":str(row.get("updated_at") or row.get("created_at") or ""),"_version":int(row.get("version") or 1)}

    def build_context(self,session_id:str,max_chars:int=12000,*,tenant_id:str|None=None)->str:
        items=list(reversed(self.list_session(session_id,100,tenant_id=tenant_id)));parts=[];used=0
        for x in items:
            line=f"[{x['evidence_id']}] {x['source_label']}: {x['content']}"
            if used+len(line)>max_chars:break
            parts.append(line);used+=len(line)+1
        return "\n".join(parts)

    @staticmethod
    def _tokens(text:str)->set[str]:return set(re.findall(r"[\w\u4e00-\u9fff]{2,}",text.lower()))

    def link_text(self,session_id:str,text:str,max_links:int=30,*,tenant_id:str|None=None)->list[dict]:
        target=self._tokens(text);links=[]
        for e in self.list_session(session_id,100,tenant_id=tenant_id):
            toks=self._tokens(e["content"]);score=len(target & toks)/max(1,len(toks))
            if score>0.08:links.append({"evidence_id":e["evidence_id"],"source_label":e["source_label"],"confidence":round(min(1.0,score),3)})
        return sorted(links,key=lambda x:x["confidence"],reverse=True)[:max_links]

    def verify_item(self,evidence_id:str,*,tenant_id:str,owner_user_id:str,decision:str,actor_user_id:str,reason:str="",confidence:float=1.0,method:str="human_review")->dict:
        mapping={"submit_review":"UNDER_REVIEW","verified":"VERIFIED","partial":"PARTIALLY_VERIFIED","rejected":"REJECTED","contradicted":"CONTRADICTED"}
        if decision not in mapping:raise ValueError("invalid evidence verification decision")
        new_status=mapping[decision];confidence=max(0.0,min(float(confidence),1.0))
        with self.engine.begin() as conn:
            row=conn.execute(text("SELECT * FROM evidence_items WHERE evidence_id=:id AND tenant_id=:tenant AND owner_user_id=:owner AND deleted_at IS NULL FOR UPDATE"),{"id":evidence_id,"tenant":tenant_id,"owner":owner_user_id}).mappings().first()
            if not row:raise KeyError(evidence_id)
            previous=str(row.get("verification_status") or ("VERIFIED" if row.get("verified") else "SELF_REPORTED"))
            conn.execute(text("""UPDATE evidence_items SET verification_status=:status,verification_method=:method,verification_confidence=:confidence,
                verified=:verified,verified_by=:actor,verified_at=CURRENT_TIMESTAMP,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE evidence_id=:id"""),
                {"status":new_status,"method":method,"confidence":confidence,"verified":1 if new_status=="VERIFIED" else 0,"actor":actor_user_id,"id":evidence_id})
            conn.execute(text("""INSERT INTO evidence_item_verification_history
                (history_id,tenant_id,session_id,evidence_id,previous_status,new_status,decision,confidence,method,reason,actor_user_id)
                VALUES(:hid,:tenant,:session,:evidence,:previous,:new,:decision,:confidence,:method,:reason,:actor)"""),
                {"hid":f"EVH-{uuid4().hex[:18].upper()}","tenant":tenant_id,"session":row.get("session_id") or "","evidence":evidence_id,"previous":previous,"new":new_status,"decision":decision,"confidence":confidence,"method":method,"reason":reason[:12000],"actor":actor_user_id})
        return self.get(evidence_id,tenant_id=tenant_id)

    def verification_history(self,evidence_id:str,*,tenant_id:str)->list[dict]:
        return [dict(x) for x in self.all("SELECT * FROM evidence_item_verification_history WHERE tenant_id=:tenant AND evidence_id=:id ORDER BY created_at DESC",{"tenant":tenant_id,"id":evidence_id})]

    def delete_session(self, session_id: str, *, tenant_id: str) -> int:
        return self.execute("DELETE FROM evidence_items WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id})
