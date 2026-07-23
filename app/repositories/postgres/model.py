from __future__ import annotations
import base64, hashlib, json
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.engine import Engine
from ...models import ProviderUpsert, RouteUpsert, ModelCapabilityUpsert
from ...model_store import ProviderRecord, RouteRecord
from ..sqlalchemy_common import SQLAlchemyRepo

class PostgresModelConfigRepository(SQLAlchemyRepo):
    def __init__(self,engine:Engine,secret_key:str):
        super().__init__(engine);digest=hashlib.sha256(secret_key.encode()).digest();self._fernet=Fernet(base64.urlsafe_b64encode(digest))
    def _encrypt(self,v:str)->str:return self._fernet.encrypt(v.encode()).decode() if v else ''
    def _decrypt(self,v:str)->str:
        if not v:return ''
        try:return self._fernet.decrypt(v.encode()).decode()
        except InvalidToken:return ''
    def upsert_provider(self,payload:ProviderUpsert)->None:
        existing=self.get_provider(payload.provider_id);enc=self._encrypt(existing.api_key if payload.api_key is None and existing else (payload.api_key or ''))
        params={'id':payload.provider_id,'name':payload.name,'kind':payload.kind,'url':payload.base_url.rstrip('/'),'key':enc,'model':payload.default_model,'enabled':1 if payload.enabled else 0,'timeout':payload.timeout_seconds,'headers':json.dumps(payload.extra_headers,ensure_ascii=False)}
        if self.one('SELECT 1 FROM llm_providers WHERE provider_id=:id',{'id':payload.provider_id}):self.execute("""UPDATE llm_providers SET name=:name,kind=:kind,base_url=:url,api_key_enc=:key,default_model=:model,enabled=:enabled,timeout_seconds=:timeout,extra_headers=:headers,updated_at=CURRENT_TIMESTAMP WHERE provider_id=:id""",params)
        else:self.execute("""INSERT INTO llm_providers(provider_id,name,kind,base_url,api_key_enc,default_model,enabled,timeout_seconds,extra_headers) VALUES(:id,:name,:kind,:url,:key,:model,:enabled,:timeout,:headers)""",params)
    def get_provider(self,provider_id:str):
        r=self.one('SELECT * FROM llm_providers WHERE provider_id=:id',{'id':provider_id})
        if not r:return None
        return ProviderRecord(provider_id=r['provider_id'],name=r['name'],kind=r['kind'],base_url=r['base_url'],api_key=self._decrypt(r['api_key_enc']),default_model=r['default_model'],enabled=bool(r['enabled']),timeout_seconds=int(r['timeout_seconds']),extra_headers=json.loads(r['extra_headers'] or '{}'))
    def list_providers(self,reveal_secret:bool=False)->list[dict]:
        out=[]
        for r in self.all('SELECT * FROM llm_providers ORDER BY name'):
            key=self._decrypt(r['api_key_enc']);out.append({'provider_id':r['provider_id'],'name':r['name'],'kind':r['kind'],'base_url':r['base_url'],'api_key':key if reveal_secret else None,'has_api_key':bool(key),'api_key_masked':(key[:4]+'••••'+key[-4:]) if len(key)>=10 else ('••••' if key else ''),'default_model':r['default_model'],'enabled':bool(r['enabled']),'timeout_seconds':int(r['timeout_seconds']),'extra_headers':json.loads(r['extra_headers'] or '{}'),'updated_at':r['updated_at']})
        return out
    def delete_provider(self,provider_id:str)->None:
        self.execute('DELETE FROM llm_routes WHERE provider_id=:id OR fallback_provider_id=:id',{'id':provider_id});self.execute('DELETE FROM llm_providers WHERE provider_id=:id',{'id':provider_id})
    def upsert_route(self,payload:RouteUpsert)->None:
        params={'task':payload.task,'provider':payload.provider_id,'model':payload.model,'fallback':payload.fallback_provider_id,'fallback_model':payload.fallback_model,'temp':payload.temperature,'max_tokens':payload.max_tokens}
        if self.one('SELECT 1 FROM llm_routes WHERE task=:task',{'task':payload.task}):self.execute("""UPDATE llm_routes SET provider_id=:provider,model=:model,fallback_provider_id=:fallback,fallback_model=:fallback_model,temperature=:temp,max_tokens=:max_tokens,updated_at=CURRENT_TIMESTAMP WHERE task=:task""",params)
        else:self.execute("""INSERT INTO llm_routes(task,provider_id,model,fallback_provider_id,fallback_model,temperature,max_tokens) VALUES(:task,:provider,:model,:fallback,:fallback_model,:temp,:max_tokens)""",params)
    def get_route(self,task:str):
        r=self.one('SELECT * FROM llm_routes WHERE task=:task',{'task':task})
        if not r:return None
        return RouteRecord(task=r['task'],provider_id=r['provider_id'],model=r['model'],fallback_provider_id=r['fallback_provider_id'],fallback_model=r['fallback_model'],temperature=float(r['temperature']),max_tokens=int(r['max_tokens']))
    def list_routes(self)->list[dict]:return [dict(r) for r in self.all('SELECT * FROM llm_routes ORDER BY task')]
    def record_usage(self,*,task:str,provider_id:str,model:str,input_tokens:int=0,output_tokens:int=0,total_tokens:int=0,latency_ms:int=0,success:bool=True,error:str='',tenant_id:str='global')->None:self.execute("""INSERT INTO llm_usage(tenant_id,task,provider_id,model,input_tokens,output_tokens,total_tokens,latency_ms,success,error) VALUES(:tenant,:task,:provider,:model,:input,:output,:total,:latency,:success,:error)""",{'tenant':tenant_id,'task':task,'provider':provider_id,'model':model,'input':input_tokens,'output':output_tokens,'total':total_tokens,'latency':latency_ms,'success':1 if success else 0,'error':error[:2000]})

    def upsert_model_capability(self,payload:ModelCapabilityUpsert)->dict:
        params={'provider':payload.provider_id,'model':payload.model,'streaming':1 if payload.supports_streaming else 0,'json_schema':1 if payload.supports_json_schema else 0,'tools':1 if payload.supports_tools else 0,'vision':1 if payload.supports_vision else 0,'files':1 if payload.supports_files else 0,'context':payload.context_window,'max_output':payload.max_output,'reasoning':payload.reasoning_level,'latency':payload.latency_class,'input_cost':payload.input_cost_per_million,'output_cost':payload.output_cost_per_million,'metadata':json.dumps(payload.metadata,ensure_ascii=False)}
        if self.one('SELECT 1 FROM llm_model_capabilities WHERE provider_id=:provider AND model=:model',params):
            self.execute("""UPDATE llm_model_capabilities SET supports_streaming=:streaming,supports_json_schema=:json_schema,supports_tools=:tools,supports_vision=:vision,supports_files=:files,context_window=:context,max_output=:max_output,reasoning_level=:reasoning,latency_class=:latency,input_cost_per_million=:input_cost,output_cost_per_million=:output_cost,metadata_json=:metadata,updated_at=CURRENT_TIMESTAMP WHERE provider_id=:provider AND model=:model""",params)
        else:
            self.execute("""INSERT INTO llm_model_capabilities(provider_id,model,supports_streaming,supports_json_schema,supports_tools,supports_vision,supports_files,context_window,max_output,reasoning_level,latency_class,input_cost_per_million,output_cost_per_million,metadata_json) VALUES(:provider,:model,:streaming,:json_schema,:tools,:vision,:files,:context,:max_output,:reasoning,:latency,:input_cost,:output_cost,:metadata)""",params)
        return self.get_model_capability(payload.provider_id,payload.model) or {}
    def get_model_capability(self,provider_id:str,model:str):
        r=self.one('SELECT * FROM llm_model_capabilities WHERE provider_id=:provider AND model=:model',{'provider':provider_id,'model':model})
        if not r:return None
        d=dict(r);d['metadata']=json.loads(d.pop('metadata_json') or '{}')
        for k in ('supports_streaming','supports_json_schema','supports_tools','supports_vision','supports_files'):d[k]=bool(d[k])
        return d
    def list_model_capabilities(self,provider_id:str|None=None)->list[dict]:
        rows=self.all('SELECT * FROM llm_model_capabilities WHERE provider_id=:provider ORDER BY model',{'provider':provider_id}) if provider_id else self.all('SELECT * FROM llm_model_capabilities ORDER BY provider_id,model')
        out=[]
        for r in rows:
            d=dict(r);d['metadata']=json.loads(d.pop('metadata_json') or '{}')
            for k in ('supports_streaming','supports_json_schema','supports_tools','supports_vision','supports_files'):d[k]=bool(d[k])
            out.append(d)
        return out
    def recommend_models(self,*,required_capabilities:list[str]|None=None,min_context_window:int=0,max_input_cost_per_million:float|None=None,max_output_cost_per_million:float|None=None,prefer_latency:str='any')->list[dict]:
        required=set(required_capabilities or []);out=[];latency_rank={'fast':0,'balanced':1,'slow':2,'unknown':3}
        for item in self.list_model_capabilities():
            provider=self.get_provider(item['provider_id'])
            if not provider or not provider.enabled:continue
            if min_context_window and int(item.get('context_window') or 0)<min_context_window:continue
            if max_input_cost_per_million is not None and float(item.get('input_cost_per_million') or 0)>max_input_cost_per_million:continue
            if max_output_cost_per_million is not None and float(item.get('output_cost_per_million') or 0)>max_output_cost_per_million:continue
            flags={'streaming':bool(item.get('supports_streaming')),'json_schema':bool(item.get('supports_json_schema')),'tools':bool(item.get('supports_tools')),'vision':bool(item.get('supports_vision')),'files':bool(item.get('supports_files'))}
            if any(not flags.get(cap,False) for cap in required):continue
            score=100.0-float(item.get('input_cost_per_million') or 0)*0.1-float(item.get('output_cost_per_million') or 0)*0.1
            if prefer_latency!='any':score-=latency_rank.get(item.get('latency_class','unknown'),3)*5
            d=dict(item);d['score']=round(score,3);out.append(d)
        return sorted(out,key=lambda x:(-x['score'],x['provider_id'],x['model']))
    def record_model_eval(self,*,eval_id:str,tenant_id:str,task:str,provider_id:str,model:str,metrics:dict,cases:list[dict])->None:
        self.execute('INSERT INTO model_eval_runs(eval_id,tenant_id,task,provider_id,model,metrics_json,cases_json) VALUES(:eval,:tenant,:task,:provider,:model,:metrics,:cases)',{'eval':eval_id,'tenant':tenant_id,'task':task,'provider':provider_id,'model':model,'metrics':json.dumps(metrics,ensure_ascii=False),'cases':json.dumps(cases,ensure_ascii=False)})
    def list_model_evals(self,tenant_id:str,limit:int=50)->list[dict]:
        out=[]
        for r in self.all('SELECT * FROM model_eval_runs WHERE tenant_id=:tenant ORDER BY created_at DESC LIMIT :limit',{'tenant':tenant_id,'limit':limit}):
            d=dict(r);d['metrics']=json.loads(d.pop('metrics_json') or '{}');d['cases']=json.loads(d.pop('cases_json') or '[]');out.append(d)
        return out
    def usage_summary(self,limit:int=100,tenant_id:str|None=None)->dict:
        params={'limit':limit};where=''
        if tenant_id is not None:where=' WHERE tenant_id=:tenant';params['tenant']=tenant_id
        rows=self.all(f'SELECT * FROM llm_usage{where} ORDER BY id DESC LIMIT :limit',params);agg=self.one(f"SELECT COUNT(*) calls,COALESCE(SUM(total_tokens),0) tokens,COALESCE(AVG(latency_ms),0) latency,COALESCE(SUM(CASE WHEN success=0 THEN 1 ELSE 0 END),0) errors FROM llm_usage{where}",params)
        return {'summary':{'calls':int(agg['calls'] or 0),'tokens':int(agg['tokens'] or 0),'average_latency_ms':round(float(agg['latency'] or 0),1),'errors':int(agg['errors'] or 0)},'recent':[dict(r) for r in rows]}
