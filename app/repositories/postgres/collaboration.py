from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ..sqlalchemy_common import SQLAlchemyRepo


class PostgresCollaborationRepository(SQLAlchemyRepo):
    def __init__(self,engine:Engine):super().__init__(engine)
    @staticmethod
    def _task_row(row)->dict:
        d=dict(row);d["payload"]=json.loads(d.pop("payload_json") or "{}");return d
    def add_feedback(self,session_id:str,content:str,teacher_name:str="Advisor",priority:str="normal",*,tenant_id:str="demo-org",teacher_user_id:str="")->dict:
        fid=f"FB-{uuid4().hex[:10].upper()}";self.execute("INSERT INTO teacher_feedback(feedback_id,session_id,tenant_id,teacher_user_id,teacher_name,content,priority) VALUES(:id,:session,:tenant,:user,:name,:content,:priority)",{"id":fid,"session":session_id,"tenant":tenant_id,"user":teacher_user_id,"name":teacher_name[:80],"content":content.strip(),"priority":priority});return self.get_feedback(fid,tenant_id=tenant_id)
    def get_feedback(self,feedback_id:str,*,tenant_id:str|None=None)->dict:
        sql="SELECT * FROM teacher_feedback WHERE feedback_id=:id";params={"id":feedback_id}
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        row=self.one(sql,params)
        if not row:raise KeyError(feedback_id)
        return dict(row)
    def list_feedback(self,session_id:str,status:str|None=None,*,tenant_id:str|None=None)->list[dict]:
        sql="SELECT * FROM teacher_feedback WHERE session_id=:session";params={"session":session_id}
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        if status:sql+=" AND status=:status";params["status"]=status
        return [dict(r) for r in self.all(sql+" ORDER BY created_at DESC",params)]
    def resolve_feedback(self,feedback_id:str,*,tenant_id:str|None=None)->None:
        sql="UPDATE teacher_feedback SET status='resolved',resolved_at=CURRENT_TIMESTAMP WHERE feedback_id=:id";params={"id":feedback_id}
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        if not self.execute(sql,params):raise KeyError(feedback_id)
    def ensure_task(self,title:str,task_type:str,session_id:str="",tenant_id:str="demo-org",priority:str="normal",source:str="system",payload:dict|None=None,owner_user_id:str="")->dict:
        row=self.one("""SELECT * FROM ai_tasks WHERE tenant_id=:tenant AND session_id=:session AND task_type=:type AND status IN ('todo','doing') ORDER BY created_at DESC LIMIT 1""",{"tenant":tenant_id,"session":session_id,"type":task_type})
        return self._task_row(row) if row else self.create_task(title,task_type,session_id,tenant_id,priority,source,payload,owner_user_id=owner_user_id)
    def create_task(self,title:str,task_type:str,session_id:str="",tenant_id:str="demo-org",priority:str="normal",source:str="system",payload:dict|None=None,*,owner_user_id:str="",task_id:str|None=None)->dict:
        tid=task_id or f"TASK-{uuid4().hex[:10].upper()}";self.execute("""INSERT INTO ai_tasks(task_id,session_id,tenant_id,owner_user_id,title,task_type,priority,source,payload_json) VALUES(:id,:session,:tenant,:owner,:title,:type,:priority,:source,:payload)""",{"id":tid,"session":session_id,"tenant":tenant_id,"owner":owner_user_id,"title":title,"type":task_type,"priority":priority,"source":source,"payload":json.dumps(payload or {},ensure_ascii=False)});return self.get_task(tid,tenant_id=tenant_id)
    def get_task(self,task_id:str,*,tenant_id:str|None=None)->dict:
        sql="SELECT * FROM ai_tasks WHERE task_id=:id";params={"id":task_id}
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        row=self.one(sql,params)
        if not row:raise KeyError(task_id)
        return self._task_row(row)
    def list_tasks(self,tenant_id:str="demo-org",status:str|None=None,limit:int=200,*,session_id:str|None=None,owner_user_id:str|None=None)->list[dict]:
        sql="SELECT * FROM ai_tasks WHERE tenant_id=:tenant";params={"tenant":tenant_id,"limit":limit}
        if status:sql+=" AND status=:status";params["status"]=status
        if session_id is not None:sql+=" AND session_id=:session";params["session"]=session_id
        if owner_user_id is not None:sql+=" AND owner_user_id=:owner";params["owner"]=owner_user_id
        sql+=" ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,updated_at DESC LIMIT :limit"
        return [self._task_row(r) for r in self.all(sql,params)]
    def update_task(self,task_id:str,status:str|None=None,priority:str|None=None,*,tenant_id:str|None=None,expected_version:int|None=None,title:str|None=None,task_type:str|None=None,source:str|None=None,payload:dict|None=None)->dict:
        current=self.get_task(task_id,tenant_id=tenant_id);actual=int(current.get("version") or 1)
        if expected_version is not None and expected_version!=actual:
            from ...unified_runtime_store import RuntimeVersionConflict
            raise RuntimeVersionConflict(task_id,expected_version,actual)
        values={"status":status if status is not None else current["status"],"priority":priority if priority is not None else current["priority"],"title":title if title is not None else current["title"],"task_type":task_type if task_type is not None else current["task_type"],"source":source if source is not None else current["source"],"payload":json.dumps(payload if payload is not None else current.get("payload") or {},ensure_ascii=False),"id":task_id}
        completed=",completed_at=CURRENT_TIMESTAMP" if values["status"] in {"done","completed"} else (",completed_at=NULL" if status is not None else "")
        sql=f"UPDATE ai_tasks SET status=:status,priority=:priority,title=:title,task_type=:task_type,source=:source,payload_json=:payload,version=version+1,updated_at=CURRENT_TIMESTAMP{completed} WHERE task_id=:id";params=values
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        if not self.execute(sql,params):raise KeyError(task_id)
        return self.get_task(task_id,tenant_id=tenant_id)

    def complete_matching(self,session_id:str,task_type:str,*,tenant_id:str|None=None)->None:
        sql="UPDATE ai_tasks SET status='done',updated_at=CURRENT_TIMESTAMP WHERE session_id=:session AND task_type=:type AND status!='done'";params={"session":session_id,"type":task_type}
        if tenant_id is not None:sql+=" AND tenant_id=:tenant";params["tenant"]=tenant_id
        self.execute(sql,params)

    def delete_session(self, session_id: str, *, tenant_id: str) -> dict:
        feedback = self.execute("DELETE FROM teacher_feedback WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id})
        tasks = self.execute("DELETE FROM ai_tasks WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id})
        return {"feedback": feedback, "tasks": tasks}
