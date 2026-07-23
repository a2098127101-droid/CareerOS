from __future__ import annotations

import csv, io, json
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import Engine
from ..sqlalchemy_common import SQLAlchemyRepo

class PostgresJobRepository(SQLAlchemyRepo):
    def __init__(self,engine:Engine):super().__init__(engine)
    @staticmethod
    def _row(row):
        d=dict(row);d['skills']=json.loads(d.pop('skills_json') or '[]');d['active']=bool(d['active']);return d
    def upsert(self,data:dict,*,tenant_id:str|None=None)->dict:
        jid=(data.get('job_id') or '').strip() or f"JOB-{uuid4().hex[:12].upper()}";skills=data.get('skills',[])
        if isinstance(skills,str):skills=[x.strip() for x in skills.replace('；',',').replace(';',',').split(',') if x.strip()]
        def num(v):
            try:return float(v) if v not in (None,'') else None
            except:return None
        tenant_id=tenant_id or str(data.get('tenant_id') or 'global')
        exists=self.one('SELECT 1 FROM jobs WHERE job_id=:id',{'id':jid})
        params={'id':jid,'tenant':tenant_id,'title':str(data.get('title','')).strip(),'company':str(data.get('company','')).strip(),'city':str(data.get('city','')).strip(),'industry':str(data.get('industry','')).strip(),'smin':num(data.get('salary_min')),'smax':num(data.get('salary_max')),'skills':json.dumps(skills,ensure_ascii=False),'desc':str(data.get('description','')).strip(),'source':str(data.get('source','manual')).strip(),'url':str(data.get('source_url','')).strip(),'active':1 if data.get('active',True) else 0}
        if exists:self.execute("""UPDATE jobs SET tenant_id=:tenant,title=:title,company=:company,city=:city,industry=:industry,salary_min=:smin,salary_max=:smax,skills_json=:skills,description=:desc,source=:source,source_url=:url,active=:active,updated_at=CURRENT_TIMESTAMP WHERE job_id=:id""",params)
        else:self.execute("""INSERT INTO jobs(job_id,tenant_id,title,company,city,industry,salary_min,salary_max,skills_json,description,source,source_url,active) VALUES(:id,:tenant,:title,:company,:city,:industry,:smin,:smax,:skills,:desc,:source,:url,:active)""",params)
        return self.get(jid,tenant_id=tenant_id)
    def get(self,job_id:str,*,tenant_id:str|None=None)->dict:
        sql='SELECT * FROM jobs WHERE job_id=:id';params={'id':job_id}
        if tenant_id is not None:sql+=" AND tenant_id IN (:tenant,'global')";params['tenant']=tenant_id
        row=self.one(sql,params)
        if not row:raise KeyError(job_id)
        return self._row(row)
    def search(self,query:str='',city:str='',industry:str='',limit:int=20,*,tenant_id:str='global')->list[dict]:
        clauses=["active=1","tenant_id IN (:tenant,'global')"];params={'tenant':tenant_id,'limit':limit}
        if query.strip():clauses.append("(lower(title) LIKE lower(:q) OR lower(company) LIKE lower(:q) OR lower(description) LIKE lower(:q) OR lower(skills_json) LIKE lower(:q))");params['q']=f"%{query.strip()}%"
        if city.strip():clauses.append("lower(city) LIKE lower(:city)");params['city']=f"%{city.strip()}%"
        if industry.strip():clauses.append("lower(industry) LIKE lower(:industry)");params['industry']=f"%{industry.strip()}%"
        return [self._row(r) for r in self.all(f"SELECT * FROM jobs WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT :limit",params)]
    def ingest_csv(self,content:bytes,source:str='csv',*,tenant_id:str='global')->dict:
        reader=csv.DictReader(io.StringIO(content.decode('utf-8-sig',errors='replace')));count=0;errors=[]
        for idx,row in enumerate(reader,start=2):
            if not (row.get('title') or '').strip():errors.append(f'第 {idx} 行缺少 title');continue
            try:row['source']=row.get('source') or source;self.upsert(row,tenant_id=tenant_id);count+=1
            except Exception as exc:errors.append(f'第 {idx} 行：{exc}')
        return {'imported':count,'errors':errors[:30]}
    def replace_requirements(self, job_id:str, requirements:list[dict], *, tenant_id:str)->int:
        self.get(job_id, tenant_id=tenant_id)
        with self.engine.begin() as conn:
            conn.execute(text("DELETE FROM job_requirements WHERE job_id=:job AND tenant_id=:tenant"), {"job":job_id,"tenant":tenant_id})
            count=0
            for item in requirements:
                rid=str(item.get('requirement_id') or f"REQ-{uuid4().hex[:14].upper()}")
                conn.execute(text("""INSERT INTO job_requirements(requirement_id,tenant_id,job_id,category,requirement_text,normalized_key,importance,source_type)
                VALUES(:rid,:tenant,:job,:category,:text,:key,:importance,:source)"""), {
                    'rid':rid,'tenant':tenant_id,'job':job_id,'category':str(item.get('category') or 'requirement'),
                    'text':str(item.get('text') or item.get('requirement_text') or ''),'key':str(item.get('normalized_key') or ''),
                    'importance':max(1,min(int(item.get('importance') or 3),5)),'source':str(item.get('source_type') or 'derived')})
                count+=1
        return count

    def list_requirements(self, job_id:str, *, tenant_id:str)->list[dict]:
        return self.all("""SELECT * FROM job_requirements WHERE job_id=:job AND tenant_id IN (:tenant,'global')
        ORDER BY CASE WHEN tenant_id=:tenant THEN 0 ELSE 1 END, importance DESC, created_at""", {'job':job_id,'tenant':tenant_id})

    def stats(self,*,tenant_id:str='global')->dict:
        row=self.one("SELECT COUNT(*) total,COUNT(DISTINCT city) cities,COUNT(DISTINCT industry) industries FROM jobs WHERE active=1 AND tenant_id IN (:tenant,'global')",{'tenant':tenant_id});return dict(row or {'total':0,'cities':0,'industries':0})
