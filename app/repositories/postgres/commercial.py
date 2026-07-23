from __future__ import annotations
import json
import hashlib
from uuid import uuid4
from datetime import datetime, timezone
from sqlalchemy.engine import Engine
from ..sqlalchemy_common import SQLAlchemyRepo
from ...commercial_store import DEFAULT_ENTITLEMENTS

class PostgresCommercialRepository(SQLAlchemyRepo):
    def __init__(self,engine:Engine):
        super().__init__(engine)
        for pid,ent in DEFAULT_ENTITLEMENTS.items():
            if not self.one('SELECT 1 FROM plans WHERE plan_id=:id',{'id':pid}):
                self.execute("INSERT INTO plans(plan_id,name,entitlements_json,active) VALUES(:id,:name,:ent,1)",{'id':pid,'name':pid.title(),'ent':json.dumps(ent,ensure_ascii=False)})
    def ensure_subscription(self,tenant_id:str,plan_id:str='free')->None:
        if not self.one('SELECT 1 FROM tenant_subscriptions WHERE tenant_id=:tenant',{'tenant':tenant_id}):self.execute("INSERT INTO tenant_subscriptions(tenant_id,plan_id,status) VALUES(:tenant,:plan,'active')",{'tenant':tenant_id,'plan':plan_id})
    def set_plan(self,tenant_id:str,plan_id:str)->None:
        if not self.one("SELECT 1 FROM plans WHERE plan_id=:id AND active=1",{'id':plan_id}):raise KeyError(plan_id)
        self.ensure_subscription(tenant_id,plan_id);self.execute("UPDATE tenant_subscriptions SET plan_id=:plan,status='active',updated_at=CURRENT_TIMESTAMP WHERE tenant_id=:tenant",{'plan':plan_id,'tenant':tenant_id})
    def subscription(self,tenant_id:str)->dict:
        self.ensure_subscription(tenant_id)
        row=self.one("""SELECT s.*,p.name AS plan_name,p.entitlements_json FROM tenant_subscriptions s JOIN plans p ON p.plan_id=s.plan_id WHERE s.tenant_id=:tenant""",{'tenant':tenant_id})
        if not row:return {'tenant_id':tenant_id,'plan_id':'free','entitlements':DEFAULT_ENTITLEMENTS['free']}
        d=dict(row);d['entitlements']=json.loads(d.pop('entitlements_json') or '{}');return d
    def entitlement(self,tenant_id:str,feature:str,default=False):return self.subscription(tenant_id).get('entitlements',{}).get(feature,default)
    def list_plans(self)->list[dict]:
        out=[]
        for r in self.all("SELECT * FROM plans WHERE active=1 ORDER BY plan_id"):
            d=dict(r);d['entitlements']=json.loads(d.pop('entitlements_json') or '{}');out.append(d)
        return out
    def track(self,*,tenant_id:str,event_name:str,user_id:str='',session_id:str='',properties:dict|None=None)->None:self.execute("INSERT INTO analytics_events(tenant_id,user_id,session_id,event_name,properties_json) VALUES(:tenant,:user,:session,:event,:props)",{'tenant':tenant_id,'user':user_id,'session':session_id,'event':event_name,'props':json.dumps(properties or {},ensure_ascii=False)})
    def analytics_summary(self,tenant_id:str)->dict:
        rows=self.all("SELECT event_name,COUNT(*) count FROM analytics_events WHERE tenant_id=:tenant GROUP BY event_name ORDER BY count DESC",{'tenant':tenant_id});uv=self.one("SELECT COUNT(DISTINCT user_id) uv FROM analytics_events WHERE tenant_id=:tenant AND user_id<>''",{'tenant':tenant_id});return {'events':{r['event_name']:int(r['count']) for r in rows},'uv':int((uv or {}).get('uv') or 0)}
    def usage_window(self,tenant_id:str)->dict[str,int]:
        # portable month boundary: calculate in Python
        now=datetime.now(timezone.utc);month_start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        try:row=self.one("SELECT COUNT(*) calls,COALESCE(SUM(total_tokens),0) tokens FROM llm_usage WHERE tenant_id=:tenant AND created_at>=:start",{'tenant':tenant_id,'start':month_start})
        except Exception:return {'calls':0,'tokens':0}
        return {'calls':int((row or {}).get('calls') or 0),'tokens':int((row or {}).get('tokens') or 0)}
    def check_ai_quota(self,tenant_id:str)->tuple[bool,str]:
        sub=self.subscription(tenant_id);ent=sub.get('entitlements',{});usage=self.usage_window(tenant_id);mc=int(ent.get('ai_calls_monthly') or 0);mt=int(ent.get('ai_tokens_monthly') or 0)
        if mc and usage['calls']>=mc:return False,f"Monthly AI call quota reached for plan {sub.get('plan_id')}"
        if mt and usage['tokens']>=mt:return False,f"Monthly AI token quota reached for plan {sub.get('plan_id')}"
        return True,''

    def create_billing_order(self,*,tenant_id:str,plan_id:str,provider:str='mock',metadata:dict|None=None)->dict:
        order_id=f"ORD-{uuid4().hex[:16].upper()}"
        self.execute("INSERT INTO billing_orders(order_id,tenant_id,plan_id,provider,metadata_json) VALUES(:id,:tenant,:plan,:provider,:meta)",{'id':order_id,'tenant':tenant_id,'plan':plan_id,'provider':provider,'meta':json.dumps(metadata or {},ensure_ascii=False)})
        return self.get_billing_order(order_id,tenant_id=tenant_id)
    def get_billing_order(self,order_id:str,*,tenant_id:str='')->dict:
        row=self.one("SELECT * FROM billing_orders WHERE order_id=:id AND tenant_id=:tenant" if tenant_id else "SELECT * FROM billing_orders WHERE order_id=:id", {'id':order_id,'tenant':tenant_id} if tenant_id else {'id':order_id})
        if not row:raise KeyError(order_id)
        d=dict(row);d['metadata']=json.loads(d.pop('metadata_json') or '{}');return d
    def record_billing_event(self,*,provider:str,event_key:str,event_type:str,tenant_id:str,raw_payload:bytes)->tuple[dict,bool]:
        existing=self.one("SELECT * FROM billing_events WHERE provider=:provider AND event_key=:key",{'provider':provider,'key':event_key})
        if existing:
            d=dict(existing);d['result']=json.loads(d.pop('result_json') or '{}');return d,True
        event_id=f"BEVT-{uuid4().hex[:16].upper()}"
        self.execute("INSERT INTO billing_events(event_id,provider,event_key,event_type,tenant_id,payload_hash) VALUES(:id,:provider,:key,:type,:tenant,:hash)",{'id':event_id,'provider':provider,'key':event_key,'type':event_type,'tenant':tenant_id,'hash':hashlib.sha256(raw_payload).hexdigest()})
        row=self.one("SELECT * FROM billing_events WHERE event_id=:id",{'id':event_id});d=dict(row);d['result']=json.loads(d.pop('result_json') or '{}');return d,False
    def complete_billing_event(self,*,provider:str,event_key:str,status:str,result:dict|None=None)->dict:
        self.execute("UPDATE billing_events SET status=:status,result_json=:result,processed_at=CURRENT_TIMESTAMP WHERE provider=:provider AND event_key=:key",{'status':status,'result':json.dumps(result or {},ensure_ascii=False),'provider':provider,'key':event_key})
        row=self.one("SELECT * FROM billing_events WHERE provider=:provider AND event_key=:key",{'provider':provider,'key':event_key})
        if not row:raise KeyError(event_key)
        d=dict(row);d['result']=json.loads(d.pop('result_json') or '{}');return d
