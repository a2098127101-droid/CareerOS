from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from ...domain_intelligence import METHODOLOGY_VERSION, json_load, norm, stable_id
from ..sqlalchemy_common import SQLAlchemyRepo


class PostgresDomainIntelligenceRepository(SQLAlchemyRepo):
    """SQLAlchemy/PostgreSQL parity repository for CareerOS v1.5 domain intelligence."""

    def __init__(self, engine: Engine):
        super().__init__(engine)

    def audit(self, *, tenant_id: str, session_id: str, actor_user_id: str, subject_user_id: str,
              entity_type: str, entity_id: str, action: str, before: dict | None = None,
              after: dict | None = None, reason: str = "", correlation_id: str = "", conn=None) -> dict:
        event_id = f"AUD-{uuid4().hex[:20].upper()}"
        params = {
            "id": event_id, "tenant": tenant_id, "session": session_id, "actor": actor_user_id,
            "subject": subject_user_id, "type": entity_type, "entity": entity_id, "action": action,
            "before": json.dumps(before or {}, ensure_ascii=False), "after": json.dumps(after or {}, ensure_ascii=False),
            "reason": reason, "corr": correlation_id,
        }
        sql = text("""INSERT INTO domain_audit_events
            (event_id,tenant_id,session_id,actor_user_id,subject_user_id,entity_type,entity_id,action,before_json,after_json,reason,correlation_id)
            VALUES(:id,:tenant,:session,:actor,:subject,:type,:entity,:action,:before,:after,:reason,:corr)""")
        if conn is not None:
            conn.execute(sql, params)
        else:
            with self.engine.begin() as cx:
                cx.execute(sql, params)
        return {"event_id": event_id, "action": action, "entity_type": entity_type, "entity_id": entity_id}

    def list_capabilities(self, *, tenant_id: str) -> list[dict]:
        rows = self.all("""SELECT * FROM capabilities WHERE status='active' AND tenant_id IN ('global',:tenant)
            ORDER BY CASE WHEN tenant_id=:tenant THEN 0 ELSE 1 END,category,name""", {"tenant": tenant_id})
        out, seen = [], set()
        for row in rows:
            item = dict(row); key = item["capability_key"]
            if key in seen: continue
            seen.add(key)
            item["aliases"] = json_load(item.pop("aliases_json", "[]"), [])
            item["level_scale"] = json_load(item.pop("level_scale_json", "{}"), {})
            out.append(item)
        return out

    def get_capability(self, capability_id: str, *, tenant_id: str) -> dict:
        row = self.one("SELECT * FROM capabilities WHERE capability_id=:id AND tenant_id IN ('global',:tenant) AND status='active'", {"id": capability_id, "tenant": tenant_id})
        if not row: raise KeyError(capability_id)
        item = dict(row); item["aliases"] = json_load(item.pop("aliases_json", "[]"), []); item["level_scale"] = json_load(item.pop("level_scale_json", "{}"), {})
        return item

    def ensure_custom_capability(self, *, tenant_id: str, name: str, category: str = "derived", actor_user_id: str = "system") -> dict:
        key = norm(name)[:120] or "custom"
        with self.engine.begin() as conn:
            row = conn.execute(text("SELECT * FROM capabilities WHERE tenant_id=:tenant AND capability_key=:key AND status='active'"), {"tenant": tenant_id, "key": key}).mappings().first()
            if row:
                capability_id = row["capability_id"]
            else:
                taxonomy_id = stable_id("TAX", tenant_id, "custom")
                if not conn.execute(text("SELECT 1 FROM capability_taxonomies WHERE taxonomy_id=:id"), {"id": taxonomy_id}).first():
                    conn.execute(text("""INSERT INTO capability_taxonomies(taxonomy_id,tenant_id,name,description,version,status,created_by)
                        VALUES(:id,:tenant,'Tenant Custom Capabilities','Tenant-scoped derived capability taxonomy',1,'active',:actor)"""), {"id": taxonomy_id, "tenant": tenant_id, "actor": actor_user_id})
                capability_id = stable_id("CAP", tenant_id, key)
                conn.execute(text("""INSERT INTO capabilities
                    (capability_id,tenant_id,taxonomy_id,capability_key,name,category,description,aliases_json,level_scale_json,version,status,created_by)
                    VALUES(:id,:tenant,:tax,:key,:name,:category,'Derived from a tenant job requirement or evidence label.',:aliases,:scale,1,'active',:actor)"""),
                    {"id": capability_id, "tenant": tenant_id, "tax": taxonomy_id, "key": key, "name": name[:160], "category": category[:80],
                     "aliases": json.dumps([name], ensure_ascii=False), "scale": json.dumps({"min":0,"max":100}), "actor": actor_user_id})
                snapshot = dict(conn.execute(text("SELECT * FROM capabilities WHERE capability_id=:id"), {"id": capability_id}).mappings().first())
                conn.execute(text("""INSERT INTO capability_versions(capability_version_id,tenant_id,capability_id,version,snapshot_json,changed_by,change_reason)
                    VALUES(:vid,:tenant,:id,1,:snap,:actor,'derived capability created')"""),
                    {"vid":f"CAPV-{uuid4().hex[:18].upper()}","tenant":tenant_id,"id":capability_id,"snap":json.dumps(snapshot,ensure_ascii=False),"actor":actor_user_id})
                self.audit(tenant_id=tenant_id,session_id="",actor_user_id=actor_user_id,subject_user_id="",entity_type="capability",entity_id=capability_id,action="created",after=snapshot,reason="derived from domain mapping",conn=conn)
        return self.get_capability(capability_id, tenant_id=tenant_id)

    def upsert_claim(self, *, tenant_id: str, session_id: str, owner_user_id: str, source_type: str,
                     source_id: str, source_locator: str, claim_text: str, claim_type: str,
                     actor_user_id: str, reason: str = "synchronized from canonical source") -> dict:
        claim_text = (claim_text or "").strip()
        if len(claim_text) < 3: raise ValueError("claim text is required")
        with self.engine.begin() as conn:
            row = conn.execute(text("""SELECT * FROM domain_claims WHERE tenant_id=:tenant AND session_id=:session AND source_type=:stype AND source_id=:sid AND source_locator=:locator"""),
                               {"tenant":tenant_id,"session":session_id,"stype":source_type,"sid":source_id,"locator":source_locator}).mappings().first()
            before = dict(row) if row else {}
            if row:
                claim_id = row["claim_id"]
                if row["claim_text"] == claim_text and row["status"] == "active" and not row["deleted_at"]: return dict(row)
                version = int(row["version"] or 1)+1
                conn.execute(text("""UPDATE domain_claims SET claim_text=:text,normalized_text=:norm,claim_type=:ctype,status='active',version=:version,updated_at=CURRENT_TIMESTAMP,deleted_at=NULL WHERE claim_id=:id"""),
                             {"text":claim_text[:12000],"norm":norm(claim_text)[:12000],"ctype":claim_type[:80],"version":version,"id":claim_id})
                action="updated"
            else:
                claim_id=stable_id("CLM",tenant_id,session_id,source_type,source_id,source_locator); version=1; action="created"
                conn.execute(text("""INSERT INTO domain_claims
                    (claim_id,tenant_id,session_id,owner_user_id,source_type,source_id,source_locator,claim_text,normalized_text,claim_type,status,version,created_by)
                    VALUES(:id,:tenant,:session,:owner,:stype,:sid,:locator,:text,:norm,:ctype,'active',1,:actor)"""),
                    {"id":claim_id,"tenant":tenant_id,"session":session_id,"owner":owner_user_id,"stype":source_type,"sid":source_id,"locator":source_locator,"text":claim_text[:12000],"norm":norm(claim_text)[:12000],"ctype":claim_type[:80],"actor":actor_user_id})
            after=dict(conn.execute(text("SELECT * FROM domain_claims WHERE claim_id=:id"),{"id":claim_id}).mappings().first())
            existing=conn.execute(text("SELECT 1 FROM domain_claim_versions WHERE claim_id=:id AND version=:version"),{"id":claim_id,"version":version}).first()
            if not existing:
                conn.execute(text("""INSERT INTO domain_claim_versions(claim_version_id,tenant_id,claim_id,version,snapshot_json,changed_by,change_reason)
                    VALUES(:vid,:tenant,:id,:version,:snap,:actor,:reason)"""),{"vid":stable_id("CLMV",claim_id,str(version)),"tenant":tenant_id,"id":claim_id,"version":version,"snap":json.dumps(after,ensure_ascii=False),"actor":actor_user_id,"reason":reason})
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id=owner_user_id,entity_type="claim",entity_id=claim_id,action=action,before=before,after=after,reason=reason,conn=conn)
            return after

    def list_claims(self, *, tenant_id: str, session_id: str, include_deleted: bool = False) -> list[dict]:
        sql="SELECT * FROM domain_claims WHERE tenant_id=:tenant AND session_id=:session"
        if not include_deleted: sql += " AND deleted_at IS NULL AND status='active'"
        sql += " ORDER BY updated_at DESC,claim_id"
        return self.all(sql,{"tenant":tenant_id,"session":session_id})

    def get_claim(self, claim_id: str, *, tenant_id: str) -> dict:
        row=self.one("SELECT * FROM domain_claims WHERE claim_id=:id AND tenant_id=:tenant",{"id":claim_id,"tenant":tenant_id})
        if not row: raise KeyError(claim_id)
        return dict(row)

    def replace_claim_evidence_links(self, *, tenant_id: str, session_id: str, claim_id: str, links: list[dict], actor_user_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            before=[dict(x) for x in conn.execute(text("SELECT * FROM claim_evidence_links WHERE tenant_id=:tenant AND claim_id=:claim"),{"tenant":tenant_id,"claim":claim_id}).mappings().all()]
            conn.execute(text("DELETE FROM claim_evidence_links WHERE tenant_id=:tenant AND claim_id=:claim"),{"tenant":tenant_id,"claim":claim_id})
            for link in links:
                relation=str(link.get("relation") or "candidate_support"); evidence_id=str(link.get("evidence_id") or "")
                conn.execute(text("""INSERT INTO claim_evidence_links
                    (link_id,tenant_id,session_id,claim_id,evidence_id,relation,confidence,verification_status,explanation,verifier_type,verified_by,version)
                    VALUES(:id,:tenant,:session,:claim,:evidence,:relation,:confidence,:status,:explanation,:verifier,:verified_by,1)"""),
                    {"id":stable_id("CEL",tenant_id,claim_id,evidence_id,relation),"tenant":tenant_id,"session":session_id,"claim":claim_id,"evidence":evidence_id,"relation":relation,"confidence":float(link.get("confidence") or 0),"status":str(link.get("verification_status") or "UNVERIFIED"),"explanation":str(link.get("explanation") or "")[:12000],"verifier":str(link.get("verifier_type") or "deterministic")[:80],"verified_by":str(link.get("verified_by") or "")[:200]})
            after=[dict(x) for x in conn.execute(text("SELECT * FROM claim_evidence_links WHERE tenant_id=:tenant AND claim_id=:claim ORDER BY confidence DESC"),{"tenant":tenant_id,"claim":claim_id}).mappings().all()]
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id="",entity_type="claim_evidence_links",entity_id=claim_id,action="recomputed",before={"items":before},after={"items":after},reason="claim verification recomputed",conn=conn)
            return after

    def replace_claim_capability_links(self, *, tenant_id: str, claim_id: str, links: list[dict], actor_user_id: str, session_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            before=[dict(x) for x in conn.execute(text("SELECT * FROM claim_capability_links WHERE tenant_id=:tenant AND claim_id=:claim"),{"tenant":tenant_id,"claim":claim_id}).mappings().all()]
            conn.execute(text("DELETE FROM claim_capability_links WHERE tenant_id=:tenant AND claim_id=:claim"),{"tenant":tenant_id,"claim":claim_id})
            for link in links:
                cap=str(link["capability_id"]); relation=str(link.get("relation") or "indicates")
                conn.execute(text("""INSERT INTO claim_capability_links(link_id,tenant_id,claim_id,capability_id,relation,confidence,explanation,version)
                    VALUES(:id,:tenant,:claim,:cap,:relation,:confidence,:explanation,1)"""),{"id":stable_id("CCL",tenant_id,claim_id,cap,relation),"tenant":tenant_id,"claim":claim_id,"cap":cap,"relation":relation,"confidence":float(link.get("confidence") or 0),"explanation":str(link.get("explanation") or "")[:12000]})
            after=[dict(x) for x in conn.execute(text("SELECT * FROM claim_capability_links WHERE tenant_id=:tenant AND claim_id=:claim ORDER BY confidence DESC"),{"tenant":tenant_id,"claim":claim_id}).mappings().all()]
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id="",entity_type="claim_capability_links",entity_id=claim_id,action="recomputed",before={"items":before},after={"items":after},reason="claim capability mapping recomputed",conn=conn)
            return after

    def version_requirements(self, *, tenant_id: str, job_id: str, requirements: list[dict], actor_user_id: str, session_id: str) -> list[dict]:
        out=[]
        with self.engine.begin() as conn:
            for req in requirements:
                rid=str(req.get("requirement_id") or "")
                if not rid: continue
                current=conn.execute(text("SELECT * FROM job_requirements WHERE tenant_id=:tenant AND job_id=:job AND requirement_id=:rid"),{"tenant":tenant_id,"job":job_id,"rid":rid}).mappings().first()
                if not current: continue
                snapshot=dict(current)
                latest=conn.execute(text("SELECT * FROM job_requirement_versions WHERE tenant_id=:tenant AND requirement_id=:rid ORDER BY version DESC LIMIT 1"),{"tenant":tenant_id,"rid":rid}).mappings().first()
                latest_snapshot=json_load(dict(latest).get("snapshot_json","{}"),{}) if latest else {}
                comparable={k:v for k,v in snapshot.items() if k not in {"version","updated_at","created_at"}}
                latest_comparable={k:v for k,v in latest_snapshot.items() if k not in {"version","updated_at","created_at"}}
                if latest and comparable==latest_comparable:
                    snapshot["version"]=int(dict(latest).get("version") or 1);out.append(snapshot);continue
                version=(int(dict(latest).get("version") or 0)+1) if latest else 1
                conn.execute(text("UPDATE job_requirements SET version=:version,updated_at=CURRENT_TIMESTAMP WHERE tenant_id=:tenant AND requirement_id=:rid"),{"version":version,"tenant":tenant_id,"rid":rid})
                snapshot=dict(conn.execute(text("SELECT * FROM job_requirements WHERE tenant_id=:tenant AND requirement_id=:rid"),{"tenant":tenant_id,"rid":rid}).mappings().first())
                conn.execute(text("""INSERT INTO job_requirement_versions(requirement_version_id,tenant_id,job_id,requirement_id,version,snapshot_json,changed_by,change_reason)
                    VALUES(:vid,:tenant,:job,:rid,:version,:snapshot,:actor,'domain recompute snapshot')"""),{"vid":stable_id("REQV",rid,str(version)),"tenant":tenant_id,"job":job_id,"rid":rid,"version":version,"snapshot":json.dumps(snapshot,ensure_ascii=False),"actor":actor_user_id})
                self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id="",entity_type="job_requirement",entity_id=rid,action="versioned",after=snapshot,reason="domain recompute snapshot",conn=conn)
                out.append(snapshot)
        return out

    def requirement_versions(self, requirement_id: str, *, tenant_id: str) -> list[dict]:
        out=[]
        for row in self.all("SELECT * FROM job_requirement_versions WHERE tenant_id=:tenant AND requirement_id=:rid ORDER BY version DESC",{"tenant":tenant_id,"rid":requirement_id}):
            item=dict(row);item["snapshot"]=json_load(item.pop("snapshot_json","{}"),{});out.append(item)
        return out

    def replace_requirement_capability_links(self, *, tenant_id: str, job_id: str, requirement_id: str, links: list[dict], actor_user_id: str, session_id: str) -> list[dict]:
        with self.engine.begin() as conn:
            before=[dict(x) for x in conn.execute(text("SELECT * FROM job_requirement_capability_links WHERE tenant_id=:tenant AND requirement_id=:req"),{"tenant":tenant_id,"req":requirement_id}).mappings().all()]
            conn.execute(text("DELETE FROM job_requirement_capability_links WHERE tenant_id=:tenant AND requirement_id=:req"),{"tenant":tenant_id,"req":requirement_id})
            for link in links:
                cap=str(link["capability_id"])
                conn.execute(text("""INSERT INTO job_requirement_capability_links
                    (link_id,tenant_id,job_id,requirement_id,capability_id,weight,minimum_score,mapping_status,explanation,version)
                    VALUES(:id,:tenant,:job,:req,:cap,:weight,:minimum,:status,:explanation,1)"""),{"id":stable_id("RCL",tenant_id,requirement_id,cap),"tenant":tenant_id,"job":job_id,"req":requirement_id,"cap":cap,"weight":float(link.get("weight") or 1),"minimum":float(link.get("minimum_score") or 60),"status":str(link.get("mapping_status") or "derived")[:80],"explanation":str(link.get("explanation") or "")[:12000]})
            after=[dict(x) for x in conn.execute(text("SELECT * FROM job_requirement_capability_links WHERE tenant_id=:tenant AND requirement_id=:req ORDER BY weight DESC"),{"tenant":tenant_id,"req":requirement_id}).mappings().all()]
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id="",entity_type="requirement_capability_links",entity_id=requirement_id,action="recomputed",before={"items":before},after={"items":after},reason="job requirement capability mapping recomputed",conn=conn)
            return after

    def _next_assessment_version(self, conn, tenant_id, session_id, capability_id):
        row=conn.execute(text("SELECT COALESCE(MAX(assessment_version),0) v FROM capability_assessments WHERE tenant_id=:tenant AND session_id=:session AND capability_id=:cap"),{"tenant":tenant_id,"session":session_id,"cap":capability_id}).mappings().first()
        return int(row["v"] or 0)+1

    def save_assessment(self, *, tenant_id: str, session_id: str, owner_user_id: str, capability_id: str,
                        potential_score: float, verified_score: float, confidence: float, explanation: dict,
                        contributions: list[dict], actor_user_id: str) -> dict:
        with self.engine.begin() as conn:
            version=self._next_assessment_version(conn,tenant_id,session_id,capability_id)
            aid=stable_id("ASM",tenant_id,session_id,capability_id,str(version))
            conn.execute(text("""INSERT INTO capability_assessments
                (assessment_id,tenant_id,session_id,owner_user_id,capability_id,assessment_version,potential_score,verified_score,confidence,methodology_version,explanation_json,created_by)
                VALUES(:id,:tenant,:session,:owner,:cap,:version,:potential,:verified,:confidence,:method,:explanation,:actor)"""),{"id":aid,"tenant":tenant_id,"session":session_id,"owner":owner_user_id,"cap":capability_id,"version":version,"potential":round(float(potential_score),3),"verified":round(float(verified_score),3),"confidence":round(float(confidence),4),"method":METHODOLOGY_VERSION,"explanation":json.dumps(explanation,ensure_ascii=False),"actor":actor_user_id})
            for c in contributions:
                conn.execute(text("""INSERT INTO capability_assessment_evidence
                    (link_id,tenant_id,assessment_id,capability_id,claim_id,evidence_id,contribution_type,potential_weight,verified_weight,explanation)
                    VALUES(:id,:tenant,:assessment,:cap,:claim,:evidence,:type,:potential,:verified,:explanation)"""),{"id":f"ASE-{uuid4().hex[:18].upper()}","tenant":tenant_id,"assessment":aid,"cap":capability_id,"claim":str(c.get("claim_id") or ""),"evidence":str(c.get("evidence_id") or ""),"type":str(c.get("contribution_type") or "candidate"),"potential":float(c.get("potential_weight") or 0),"verified":float(c.get("verified_weight") or 0),"explanation":str(c.get("explanation") or "")[:12000]})
            result=dict(conn.execute(text("SELECT * FROM capability_assessments WHERE assessment_id=:id"),{"id":aid}).mappings().first())
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id=owner_user_id,entity_type="capability_assessment",entity_id=aid,action="calculated",after=result,reason=METHODOLOGY_VERSION,conn=conn)
        result["explanation"]=json_load(result.pop("explanation_json","{}"),{}); result["contributions"]=contributions; return result

    def latest_assessments(self, *, tenant_id: str, session_id: str) -> list[dict]:
        rows=self.all("""SELECT a.*,c.name capability_name,c.capability_key,c.category FROM capability_assessments a
            JOIN capabilities c ON c.capability_id=a.capability_id
            JOIN (SELECT capability_id,MAX(assessment_version) v FROM capability_assessments WHERE tenant_id=:tenant AND session_id=:session GROUP BY capability_id) latest
              ON latest.capability_id=a.capability_id AND latest.v=a.assessment_version
            WHERE a.tenant_id=:tenant AND a.session_id=:session ORDER BY a.verified_score DESC,a.potential_score DESC,c.name""",{"tenant":tenant_id,"session":session_id})
        out=[]
        for row in rows:
            item=dict(row); item["explanation"]=json_load(item.pop("explanation_json","{}"),{})
            item["contributions"]=self.all("SELECT * FROM capability_assessment_evidence WHERE tenant_id=:tenant AND assessment_id=:id ORDER BY verified_weight DESC,potential_weight DESC",{"tenant":tenant_id,"id":item["assessment_id"]})
            out.append(item)
        return out

    def upsert_gap(self, *, tenant_id: str, session_id: str, owner_user_id: str, job_id: str,
                   requirement_id: str, capability_id: str, gap_type: str, severity: float,
                   potential_score: float, verified_score: float, required_score: float,
                   explanation: dict, actor_user_id: str) -> dict:
        with self.engine.begin() as conn:
            row=conn.execute(text("""SELECT * FROM career_gaps WHERE tenant_id=:tenant AND session_id=:session AND job_id=:job AND requirement_id=:req AND capability_id=:cap"""),{"tenant":tenant_id,"session":session_id,"job":job_id,"req":requirement_id,"cap":capability_id}).mappings().first()
            before=dict(row) if row else {}
            if row:
                gid=row["gap_id"]; version=int(row["version"] or 1)+1
                conn.execute(text("""UPDATE career_gaps SET gap_type=:type,severity=:severity,status='open',version=:version,potential_score=:potential,verified_score=:verified,required_score=:required,explanation_json=:explanation,updated_at=CURRENT_TIMESTAMP,deleted_at=NULL WHERE gap_id=:id"""),{"type":gap_type,"severity":severity,"version":version,"potential":potential_score,"verified":verified_score,"required":required_score,"explanation":json.dumps(explanation,ensure_ascii=False),"id":gid})
            else:
                gid=stable_id("GAP",tenant_id,session_id,job_id,requirement_id,capability_id); version=1
                conn.execute(text("""INSERT INTO career_gaps
                    (gap_id,tenant_id,session_id,owner_user_id,job_id,requirement_id,capability_id,gap_type,severity,status,version,potential_score,verified_score,required_score,explanation_json,created_by)
                    VALUES(:id,:tenant,:session,:owner,:job,:req,:cap,:type,:severity,'open',1,:potential,:verified,:required,:explanation,:actor)"""),{"id":gid,"tenant":tenant_id,"session":session_id,"owner":owner_user_id,"job":job_id,"req":requirement_id,"cap":capability_id,"type":gap_type,"severity":severity,"potential":potential_score,"verified":verified_score,"required":required_score,"explanation":json.dumps(explanation,ensure_ascii=False),"actor":actor_user_id})
            after=dict(conn.execute(text("SELECT * FROM career_gaps WHERE gap_id=:id"),{"id":gid}).mappings().first())
            existing=conn.execute(text("SELECT 1 FROM career_gap_versions WHERE gap_id=:id AND version=:version"),{"id":gid,"version":version}).first()
            if not existing:
                conn.execute(text("""INSERT INTO career_gap_versions(gap_version_id,tenant_id,gap_id,version,snapshot_json,changed_by,change_reason)
                    VALUES(:vid,:tenant,:id,:version,:snap,:actor,'domain recompute')"""),{"vid":stable_id("GAPV",gid,str(version)),"tenant":tenant_id,"id":gid,"version":version,"snap":json.dumps(after,ensure_ascii=False),"actor":actor_user_id})
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id=owner_user_id,entity_type="gap",entity_id=gid,action="updated" if before else "created",before=before,after=after,reason="requirement/capability comparison",conn=conn)
        after["explanation"]=json_load(after.pop("explanation_json","{}"),{}); return after

    def list_gaps(self, *, tenant_id: str, session_id: str, job_id: str = "") -> list[dict]:
        sql="""SELECT g.*,r.requirement_text,r.category requirement_category,c.name capability_name,c.capability_key
            FROM career_gaps g JOIN job_requirements r ON r.requirement_id=g.requirement_id LEFT JOIN capabilities c ON c.capability_id=g.capability_id
            WHERE g.tenant_id=:tenant AND g.session_id=:session AND g.deleted_at IS NULL"""; params={"tenant":tenant_id,"session":session_id}
        if job_id: sql += " AND g.job_id=:job"; params["job"]=job_id
        sql += " ORDER BY g.severity DESC,g.updated_at DESC"
        out=[]
        for row in self.all(sql,params):
            item=dict(row); item["explanation"]=json_load(item.pop("explanation_json","{}"),{}); out.append(item)
        return out

    def explain_capability(self, capability_id: str, *, tenant_id: str, session_id: str) -> dict:
        capability=self.get_capability(capability_id,tenant_id=tenant_id)
        assessments=[x for x in self.latest_assessments(tenant_id=tenant_id,session_id=session_id) if x["capability_id"]==capability_id]
        claims=[dict(x) for x in self.all("""SELECT c.*,l.relation,l.confidence link_confidence,l.explanation link_explanation
            FROM claim_capability_links l JOIN domain_claims c ON c.claim_id=l.claim_id
            WHERE l.tenant_id=:tenant AND l.capability_id=:cap AND c.session_id=:session AND c.deleted_at IS NULL ORDER BY l.confidence DESC""",{"tenant":tenant_id,"cap":capability_id,"session":session_id})]
        for claim in claims:
            claim["evidence_links"]=[dict(x) for x in self.all("SELECT * FROM claim_evidence_links WHERE tenant_id=:tenant AND claim_id=:claim ORDER BY confidence DESC",{"tenant":tenant_id,"claim":claim["claim_id"]})]
        return {"capability":capability,"latest_assessment":assessments[0] if assessments else None,"claims":claims,"methodology_version":METHODOLOGY_VERSION}

    def claim_capability_links_for_session(self, *, tenant_id: str, session_id: str) -> list[dict]:
        return [dict(x) for x in self.all("""SELECT l.* FROM claim_capability_links l JOIN domain_claims c ON c.claim_id=l.claim_id
            WHERE l.tenant_id=:tenant AND c.tenant_id=:tenant AND c.session_id=:session AND c.deleted_at IS NULL""",
            {"tenant":tenant_id,"session":session_id})]

    def claim_evidence_links_for_session(self, *, tenant_id: str, session_id: str) -> list[dict]:
        return [dict(x) for x in self.all("""SELECT l.* FROM claim_evidence_links l JOIN domain_claims c ON c.claim_id=l.claim_id
            WHERE l.tenant_id=:tenant AND c.tenant_id=:tenant AND c.session_id=:session AND c.deleted_at IS NULL""",
            {"tenant":tenant_id,"session":session_id})]

    def requirement_links_for_job(self, *, tenant_id: str, job_id: str) -> list[dict]:
        return [dict(x) for x in self.all("SELECT * FROM job_requirement_capability_links WHERE tenant_id=:tenant AND job_id=:job ORDER BY requirement_id,weight DESC",
            {"tenant":tenant_id,"job":job_id})]

    def update_claim(self, *, tenant_id: str, session_id: str, owner_user_id: str, claim_id: str,
                     claim_text: str, claim_type: str, actor_user_id: str, expected_version: int | None = None,
                     reason: str = "manual claim edit") -> dict:
        with self.engine.begin() as conn:
            row = conn.execute(text("""SELECT * FROM domain_claims WHERE claim_id=:id AND tenant_id=:tenant
                AND session_id=:session AND owner_user_id=:owner AND deleted_at IS NULL"""),
                {"id":claim_id,"tenant":tenant_id,"session":session_id,"owner":owner_user_id}).mappings().first()
            if not row: raise KeyError(claim_id)
            before=dict(row); actual=int(before.get("version") or 1)
            if expected_version is not None and expected_version != actual:
                from ...domain_intelligence import DomainVersionConflict
                raise DomainVersionConflict(claim_id, expected_version, actual)
            version=actual+1
            conn.execute(text("""UPDATE domain_claims SET claim_text=:text,normalized_text=:norm,claim_type=:ctype,
                version=:version,updated_at=CURRENT_TIMESTAMP WHERE claim_id=:id"""),
                {"text":(claim_text or "").strip()[:12000],"norm":norm(claim_text)[:12000],"ctype":claim_type[:80],"version":version,"id":claim_id})
            after=dict(conn.execute(text("SELECT * FROM domain_claims WHERE claim_id=:id"),{"id":claim_id}).mappings().first())
            conn.execute(text("""INSERT INTO domain_claim_versions
                (claim_version_id,tenant_id,claim_id,version,snapshot_json,changed_by,change_reason)
                VALUES(:vid,:tenant,:id,:version,:snapshot,:actor,:reason)"""),
                {"vid":stable_id("CLMV",claim_id,str(version)),"tenant":tenant_id,"id":claim_id,"version":version,
                 "snapshot":json.dumps(after,ensure_ascii=False),"actor":actor_user_id,"reason":reason})
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id=owner_user_id,
                entity_type="claim",entity_id=claim_id,action="updated",before=before,after=after,reason=reason,conn=conn)
            return after

    def claim_versions(self, claim_id: str, *, tenant_id: str) -> list[dict]:
        out=[]
        for row in self.all("SELECT * FROM domain_claim_versions WHERE tenant_id=:tenant AND claim_id=:id ORDER BY version DESC",{"tenant":tenant_id,"id":claim_id}):
            item=dict(row); item["snapshot"]=json_load(item.pop("snapshot_json","{}"),{}); out.append(item)
        return out

    def requirement_mappings(self, *, tenant_id: str, job_id: str) -> list[dict]:
        return [dict(x) for x in self.all("""SELECT l.*,r.requirement_text,r.category requirement_category,r.importance,
            c.name capability_name,c.capability_key FROM job_requirement_capability_links l
            JOIN job_requirements r ON r.requirement_id=l.requirement_id
            JOIN capabilities c ON c.capability_id=l.capability_id
            WHERE l.tenant_id=:tenant AND l.job_id=:job ORDER BY r.importance DESC,l.weight DESC""",{"tenant":tenant_id,"job":job_id})]

    def assessment_versions(self, capability_id: str, *, tenant_id: str, session_id: str) -> list[dict]:
        out=[]
        for row in self.all("""SELECT * FROM capability_assessments WHERE tenant_id=:tenant AND session_id=:session
            AND capability_id=:cap ORDER BY assessment_version DESC""",{"tenant":tenant_id,"session":session_id,"cap":capability_id}):
            item=dict(row); item["explanation"]=json_load(item.pop("explanation_json","{}"),{}); out.append(item)
        return out

    def gap_versions(self, gap_id: str, *, tenant_id: str) -> list[dict]:
        out=[]
        for row in self.all("SELECT * FROM career_gap_versions WHERE tenant_id=:tenant AND gap_id=:id ORDER BY version DESC",{"tenant":tenant_id,"id":gap_id}):
            item=dict(row); item["snapshot"]=json_load(item.pop("snapshot_json","{}"),{}); out.append(item)
        return out

    def update_gap_status(self, *, tenant_id: str, session_id: str, owner_user_id: str, gap_id: str, status: str,
                          actor_user_id: str, expected_version: int | None = None, reason: str = "gap status update") -> dict:
        if status not in {"open","planned","in_progress","resolved","accepted","dismissed"}:
            raise ValueError("invalid gap status")
        with self.engine.begin() as conn:
            row=conn.execute(text("""SELECT * FROM career_gaps WHERE gap_id=:id AND tenant_id=:tenant AND session_id=:session
                AND owner_user_id=:owner AND deleted_at IS NULL"""),{"id":gap_id,"tenant":tenant_id,"session":session_id,"owner":owner_user_id}).mappings().first()
            if not row: raise KeyError(gap_id)
            before=dict(row); actual=int(before.get("version") or 1)
            if expected_version is not None and expected_version != actual:
                from ...domain_intelligence import DomainVersionConflict
                raise DomainVersionConflict(gap_id, expected_version, actual)
            version=actual+1
            conn.execute(text("UPDATE career_gaps SET status=:status,version=:version,updated_at=CURRENT_TIMESTAMP WHERE gap_id=:id"),{"status":status,"version":version,"id":gap_id})
            after=dict(conn.execute(text("SELECT * FROM career_gaps WHERE gap_id=:id"),{"id":gap_id}).mappings().first())
            conn.execute(text("""INSERT INTO career_gap_versions
                (gap_version_id,tenant_id,gap_id,version,snapshot_json,changed_by,change_reason)
                VALUES(:vid,:tenant,:id,:version,:snapshot,:actor,:reason)"""),
                {"vid":stable_id("GAPV",gap_id,str(version)),"tenant":tenant_id,"id":gap_id,"version":version,
                 "snapshot":json.dumps(after,ensure_ascii=False),"actor":actor_user_id,"reason":reason})
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id=owner_user_id,
                entity_type="gap",entity_id=gap_id,action="status_changed",before=before,after=after,reason=reason,conn=conn)
        after["explanation"]=json_load(after.pop("explanation_json","{}"),{}); return after

    def audit_events(self, *, tenant_id: str, session_id: str = "", entity_type: str = "", entity_id: str = "", limit: int = 200) -> list[dict]:
        sql="SELECT * FROM domain_audit_events WHERE tenant_id=:tenant"; params={"tenant":tenant_id,"limit":max(1,min(limit,1000))}
        if session_id: sql += " AND session_id=:session"; params["session"]=session_id
        if entity_type: sql += " AND entity_type=:type"; params["type"]=entity_type
        if entity_id: sql += " AND entity_id=:entity"; params["entity"]=entity_id
        sql += " ORDER BY created_at DESC LIMIT :limit"
        out=[]
        for row in self.all(sql,params):
            item=dict(row); item["before"]=json_load(item.pop("before_json","{}"),{}); item["after"]=json_load(item.pop("after_json","{}"),{}); out.append(item)
        return out
