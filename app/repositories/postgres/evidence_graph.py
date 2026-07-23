from __future__ import annotations
import hashlib, json, re
from uuid import uuid4
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine
from ..sqlalchemy_common import SQLAlchemyRepo

_SENTENCE_SPLIT=re.compile(r'(?<=[。！？!?])|\n+')
def _fingerprint(t:str)->str:return hashlib.sha256(re.sub(r'\s+','',t).lower().encode()).hexdigest()[:24]
def _tokens(t:str)->set[str]:
    v=re.sub(r'\s+','',t.lower());english=re.findall(r'[a-z0-9_+-]{2,}',v);cn=re.findall(r'[\u4e00-\u9fff]+',v);grams=[]
    for run in cn:
        grams.extend(run[i:i+2] for i in range(max(0,len(run)-1)))
        if len(run)<=8:grams.append(run)
    return set(english+grams+re.findall(r'\d+(?:\.\d+)?%?',v))
def _support_score(claim:str,evidence:str)->float:
    a,b=_tokens(claim),_tokens(evidence)
    if not a or not b:return 0.0
    overlap=len(a&b)/max(1,min(len(a),len(b)));cn=set(re.findall(r'\d+(?:\.\d+)?%?',claim));en=set(re.findall(r'\d+(?:\.\d+)?%?',evidence))
    if cn:overlap+=0.2 if cn<=en else -0.25
    return max(0.0,min(0.99,overlap))

class PostgresEvidenceGraphRepository(SQLAlchemyRepo):
    def __init__(self,engine:Engine):super().__init__(engine)
    def _edge(self,conn,*,tenant_id,session_id,from_type,from_id,relation,to_type,to_id,confidence=1.0,metadata=None):
        p={'tenant':tenant_id,'ft':from_type,'fid':from_id,'rel':relation,'tt':to_type,'tid':to_id};row=conn.execute(text("SELECT edge_id FROM evidence_graph_edges WHERE tenant_id=:tenant AND from_type=:ft AND from_id=:fid AND relation=:rel AND to_type=:tt AND to_id=:tid"),p).mappings().first()
        meta=json.dumps(metadata or {},ensure_ascii=False)
        if row:conn.execute(text('UPDATE evidence_graph_edges SET confidence=:c,metadata_json=:m WHERE edge_id=:id'),{'c':float(confidence),'m':meta,'id':row['edge_id']});return row['edge_id']
        eid=f"EDGE-{uuid4().hex[:12].upper()}";conn.execute(text("""INSERT INTO evidence_graph_edges(edge_id,tenant_id,session_id,from_type,from_id,relation,to_type,to_id,confidence,metadata_json) VALUES(:id,:tenant,:session,:ft,:fid,:rel,:tt,:tid,:c,:m)"""),{'id':eid,'tenant':tenant_id,'session':session_id,'ft':from_type,'fid':from_id,'rel':relation,'tt':to_type,'tid':to_id,'c':float(confidence),'m':meta});return eid
    def _claim(self,conn,*,tenant_id,session_id,text_value,claim_type,status='unverified'):
        fp=_fingerprint(text_value);row=conn.execute(text('SELECT claim_id FROM evidence_claims WHERE tenant_id=:tenant AND session_id=:session AND fingerprint=:fp AND claim_type=:type'),{'tenant':tenant_id,'session':session_id,'fp':fp,'type':claim_type}).mappings().first()
        if row:return row['claim_id']
        cid=f"CLM-{uuid4().hex[:12].upper()}";conn.execute(text("INSERT INTO evidence_claims(claim_id,tenant_id,session_id,claim_text,claim_type,status,fingerprint) VALUES(:id,:tenant,:session,:text,:type,:status,:fp)"),{'id':cid,'tenant':tenant_id,'session':session_id,'text':text_value[:4000],'type':claim_type,'status':status,'fp':fp});return cid
    def trace_artifact_version(self,*,tenant_id,session_id,artifact_id,version_id,content,evidence_items):
        sentences=[s.strip() for s in _SENTENCE_SPLIT.split(content or '') if len(s.strip())>=8];linked=unsupported=0;ids=[]
        with self.engine.begin() as conn:
            self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='artifact',from_id=artifact_id,relation='has_version',to_type='artifact_version',to_id=version_id)
            for idx,s in enumerate(sentences[:300]):
                cid=self._claim(conn,tenant_id=tenant_id,session_id=session_id,text_value=s,claim_type='artifact_claim');ids.append(cid);self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='artifact_version',from_id=version_id,relation='contains_claim',to_type='claim',to_id=cid,metadata={'sentence_index':idx})
                ranked=sorted([(_support_score(s,i.get('content','')),i) for i in evidence_items if _support_score(s,i.get('content',''))>=.34],key=lambda x:x[0],reverse=True)
                for score,item in ranked[:3]:self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='claim',from_id=cid,relation='supported_by',to_type='evidence',to_id=item['evidence_id'],confidence=score,metadata={'source_label':item.get('source_label','')});linked+=1
                if not ranked:unsupported+=1
        return {'artifact_id':artifact_id,'version_id':version_id,'claims':len(ids),'evidence_links':linked,'unsupported_claims':unsupported}
    def record_review(self,*,tenant_id,session_id,artifact_id,version_id,report,created_by=''):
        rid=f"REV-{uuid4().hex[:12].upper()}";findings=[]
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO review_records(review_id,tenant_id,session_id,artifact_id,version_id,total_score,report_json,created_by) VALUES(:id,:tenant,:session,:artifact,:version,:score,:report,:by)"),{'id':rid,'tenant':tenant_id,'session':session_id,'artifact':artifact_id,'version':version_id,'score':int(report.get('total_score') or 0),'report':json.dumps(report,ensure_ascii=False),'by':created_by})
            if version_id:self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='review',from_id=rid,relation='evaluates',to_type='artifact_version',to_id=version_id)
            for key,ctype in [('fatal_issues','review_finding'),('structural_issues','review_finding'),('revision_priority','review_recommendation')]:
                for item in report.get(key,[]) or []:
                    if not str(item).strip():continue
                    cid=self._claim(conn,tenant_id=tenant_id,session_id=session_id,text_value=str(item),claim_type=ctype,status='reviewer_generated');findings.append(cid);self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='review',from_id=rid,relation='produces_finding',to_type='claim',to_id=cid)
        return {'review_id':rid,'artifact_id':artifact_id,'version_id':version_id,'findings':findings}
    def record_feedback(self,*,tenant_id,session_id,feedback_id,content,artifact_id='',version_id=''):
        with self.engine.begin() as conn:
            cid=self._claim(conn,tenant_id=tenant_id,session_id=session_id,text_value=content,claim_type='teacher_guidance',status='human_guidance');self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='feedback',from_id=feedback_id,relation='expresses',to_type='claim',to_id=cid)
            if version_id:self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='feedback',from_id=feedback_id,relation='targets',to_type='artifact_version',to_id=version_id)
            elif artifact_id:self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='feedback',from_id=feedback_id,relation='targets',to_type='artifact',to_id=artifact_id)
        return {'feedback_id':feedback_id,'claim_id':cid}
    def link_revision(self,*,tenant_id,session_id,previous_version_id,new_version_id,review_id='',feedback_ids=None):
        with self.engine.begin() as conn:
            if previous_version_id and new_version_id:self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='artifact_version',from_id=new_version_id,relation='revises',to_type='artifact_version',to_id=previous_version_id)
            if review_id and new_version_id:self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='artifact_version',from_id=new_version_id,relation='responds_to',to_type='review',to_id=review_id)
            for fid in feedback_ids or []:self._edge(conn,tenant_id=tenant_id,session_id=session_id,from_type='artifact_version',from_id=new_version_id,relation='responds_to',to_type='feedback',to_id=fid)
    def latest_review(self,session_id:str,*,tenant_id:str):
        r=self.one("SELECT * FROM review_records WHERE session_id=:session AND tenant_id=:tenant ORDER BY created_at DESC LIMIT 1",{'session':session_id,'tenant':tenant_id})
        if not r:return None
        d=dict(r);d['report']=json.loads(d.pop('report_json') or '{}');return d
    def session_graph(self,session_id:str,*,tenant_id:str)->dict:
        claims=[dict(r) for r in self.all('SELECT * FROM evidence_claims WHERE session_id=:session AND tenant_id=:tenant ORDER BY created_at',{'session':session_id,'tenant':tenant_id})];edges=[dict(r) for r in self.all('SELECT * FROM evidence_graph_edges WHERE session_id=:session AND tenant_id=:tenant ORDER BY created_at',{'session':session_id,'tenant':tenant_id})];reviews=[dict(r) for r in self.all('SELECT * FROM review_records WHERE session_id=:session AND tenant_id=:tenant ORDER BY created_at',{'session':session_id,'tenant':tenant_id})]
        for e in edges:
            try:e['metadata']=json.loads(e.pop('metadata_json') or '{}')
            except:e['metadata']={}
        for r in reviews:
            try:r['report']=json.loads(r.pop('report_json') or '{}')
            except:r['report']={}
        histories=[dict(r) for r in self.all('SELECT * FROM evidence_verification_history WHERE session_id=:session AND tenant_id=:tenant ORDER BY created_at',{'session':session_id,'tenant':tenant_id})];return {'claims':claims,'edges':edges,'reviews':reviews,'verification_history':histories}
    def list_claims(self,session_id:str,*,tenant_id:str,claim_ids:list[str]|None=None)->list[dict]:
        if claim_ids:
            stmt=text('SELECT * FROM evidence_claims WHERE session_id=:session AND tenant_id=:tenant AND claim_id IN :ids ORDER BY created_at').bindparams(bindparam('ids',expanding=True))
            with self.engine.connect() as conn:return [dict(r) for r in conn.execute(stmt,{'session':session_id,'tenant':tenant_id,'ids':claim_ids}).mappings().all()]
        return [dict(r) for r in self.all('SELECT * FROM evidence_claims WHERE session_id=:session AND tenant_id=:tenant ORDER BY created_at',{'session':session_id,'tenant':tenant_id})]
    def update_claim_verification(self, claim_id: str, *, tenant_id: str, status: str, confidence: float,
                                  verified_by: str = 'system', verifier_type: str = 'ai', reason: str = '',
                                  session_id: str = '', risk_level: str = 'normal',
                                  requires_human_review: bool = False) -> dict:
        allowed = {'SUPPORTED','PARTIALLY_SUPPORTED','CONTRADICTED','UNSUPPORTED','UNVERIFIED'}
        if status not in allowed:
            raise ValueError('invalid verification status')
        with self.engine.begin() as conn:
            before = conn.execute(text('SELECT * FROM evidence_claims WHERE claim_id=:id AND tenant_id=:tenant'), {'id': claim_id, 'tenant': tenant_id}).mappings().first()
            if not before:
                raise KeyError(claim_id)
            previous = before.get('verification_status') or 'UNVERIFIED'
            resolved_session = session_id or before.get('session_id', '')
            conn.execute(text("""UPDATE evidence_claims SET verification_status=:status,verification_confidence=:confidence,verified_by=:by,
            verified_at=CURRENT_TIMESTAMP,risk_level=:risk,requires_human_review=:human,updated_at=CURRENT_TIMESTAMP
            WHERE claim_id=:id AND tenant_id=:tenant"""), {
                'status': status, 'confidence': float(confidence), 'by': verified_by, 'risk': risk_level,
                'human': 1 if requires_human_review else 0, 'id': claim_id, 'tenant': tenant_id,
            })
            conn.execute(text("""INSERT INTO evidence_verification_history(verification_id,tenant_id,session_id,claim_id,previous_status,new_status,confidence,verifier_type,verified_by,reason,risk_level,requires_human_review)
            VALUES(:vid,:tenant,:session,:claim,:previous,:new,:confidence,:vtype,:by,:reason,:risk,:human)"""), {
                'vid': f"VFY-{uuid4().hex[:14].upper()}", 'tenant': tenant_id, 'session': resolved_session, 'claim': claim_id,
                'previous': previous, 'new': status, 'confidence': float(confidence), 'vtype': verifier_type, 'by': verified_by,
                'reason': reason[:4000], 'risk': risk_level, 'human': 1 if requires_human_review else 0,
            })
            row = conn.execute(text('SELECT * FROM evidence_claims WHERE claim_id=:id AND tenant_id=:tenant'), {'id': claim_id, 'tenant': tenant_id}).mappings().first()
        return dict(row)

    def verification_history(self,claim_id:str,*,tenant_id:str)->list[dict]:
        return [dict(r) for r in self.all('SELECT * FROM evidence_verification_history WHERE claim_id=:claim AND tenant_id=:tenant ORDER BY created_at',{'claim':claim_id,'tenant':tenant_id})]
    def artifact_trace(self,artifact_id:str,*,tenant_id:str)->dict:
        versions=[dict(r) for r in self.all('SELECT * FROM artifact_versions WHERE artifact_id=:artifact AND tenant_id=:tenant ORDER BY version',{'artifact':artifact_id,'tenant':tenant_id})];vids=[v['version_id'] for v in versions]
        if not vids:return {'artifact_id':artifact_id,'versions':[],'claims':[],'edges':[],'evidence':[],'reviews':[]}
        stmt=text("""SELECT * FROM evidence_graph_edges WHERE tenant_id=:tenant AND ((from_type='artifact' AND from_id=:artifact) OR (from_type='artifact_version' AND from_id IN :vids) OR (to_type='artifact_version' AND to_id IN :vids)) ORDER BY created_at""").bindparams(bindparam('vids',expanding=True));
        with self.engine.connect() as conn:edges=[dict(r) for r in conn.execute(stmt,{'tenant':tenant_id,'artifact':artifact_id,'vids':vids}).mappings().all()]
        cids={e['to_id'] for e in edges if e['to_type']=='claim'}|{e['from_id'] for e in edges if e['from_type']=='claim'};claims=[];evidence=[]
        if cids:
            stmt=text('SELECT * FROM evidence_claims WHERE tenant_id=:tenant AND claim_id IN :ids').bindparams(bindparam('ids',expanding=True));
            with self.engine.connect() as conn:claims=[dict(r) for r in conn.execute(stmt,{'tenant':tenant_id,'ids':list(cids)}).mappings().all()]
            stmt=text('SELECT * FROM evidence_graph_edges WHERE tenant_id=:tenant AND (from_id IN :ids OR to_id IN :ids) ORDER BY created_at').bindparams(bindparam('ids',expanding=True));
            with self.engine.connect() as conn:extra=[dict(r) for r in conn.execute(stmt,{'tenant':tenant_id,'ids':list(cids)}).mappings().all()]
            known={e['edge_id'] for e in edges};edges.extend(e for e in extra if e['edge_id'] not in known)
        eids={e['to_id'] for e in edges if e['to_type']=='evidence'}|{e['from_id'] for e in edges if e['from_type']=='evidence'}
        if eids:
            stmt=text('SELECT * FROM evidence_items WHERE tenant_id=:tenant AND evidence_id IN :ids').bindparams(bindparam('ids',expanding=True));
            with self.engine.connect() as conn:evidence=[dict(r) for r in conn.execute(stmt,{'tenant':tenant_id,'ids':list(eids)}).mappings().all()]
        reviews=[dict(r) for r in self.all('SELECT * FROM review_records WHERE artifact_id=:artifact AND tenant_id=:tenant ORDER BY created_at',{'artifact':artifact_id,'tenant':tenant_id})]
        return {'artifact_id':artifact_id,'versions':versions,'claims':claims,'edges':edges,'evidence':evidence,'reviews':reviews}

    def delete_session(self, session_id: str, *, tenant_id: str) -> dict:
        edges = self.execute("DELETE FROM evidence_graph_edges WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id})
        reviews = self.execute("DELETE FROM review_records WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id})
        history = self.execute("DELETE FROM evidence_verification_history WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id})
        claims = self.execute("DELETE FROM evidence_claims WHERE session_id=:session AND tenant_id=:tenant", {"session": session_id, "tenant": tenant_id})
        return {"claims": claims, "reviews": reviews, "edges": edges, "verification_history": history}
