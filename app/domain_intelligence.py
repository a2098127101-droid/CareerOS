from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

from .evidence_verification import (
    EvidenceVerificationService,
    STATUS_CONTRADICTED,
    STATUS_PARTIAL,
    STATUS_SUPPORTED,
    STATUS_UNSUPPORTED,
    STATUS_UNVERIFIED,
)

METHODOLOGY_VERSION = "career-capability-v1.5-deterministic"
TRUST_WEIGHTS = {
    "SELF_REPORTED": 0.25,
    "SOURCE_ATTACHED": 0.4,
    "EXTRACTED": 0.45,
    "AI_ASSESSED": 0.5,
    "UNDER_REVIEW": 0.5,
    "PARTIALLY_VERIFIED": 0.7,
    "VERIFIED": 1.0,
    "REJECTED": 0.0,
    "CONTRADICTED": -0.5,
}
VERIFIED_STATES = {"VERIFIED"}
PARTIAL_TRUST_STATES = {"PARTIALLY_VERIFIED"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff+#]+", "", (text or "").lower())


def tokens(text: str) -> set[str]:
    value = (text or "").lower()
    en = re.findall(r"[a-z0-9+#.]{2,}", value)
    cn = re.findall(r"[\u4e00-\u9fff]{2,}", value)
    out = set(en)
    for run in cn:
        if len(run) <= 10:
            out.add(run)
        out.update(run[i : i + 2] for i in range(max(0, len(run) - 1)))
    return out


def overlap(a: str, b: str) -> float:
    aa, bb = tokens(a), tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, min(len(aa), len(bb)))


def stable_id(prefix: str, *parts: str, length: int = 20) -> str:
    raw = "|".join(str(x or "") for x in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:length].upper()
    return f"{prefix}-{digest}"


def json_load(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except Exception:
        return default


class DomainVersionConflict(RuntimeError):
    def __init__(self, entity_id: str, expected: int, actual: int):
        super().__init__(f"version conflict for {entity_id}: expected {expected}, actual {actual}")
        self.entity_id, self.expected, self.actual = entity_id, expected, actual


class DomainIntelligenceStore:
    """SQLite canonical repository for the v1.5 domain-intelligence graph.

    Every first-class entity is tenant/session scoped, versioned, and accompanied by audit snapshots.
    The repository stores facts and calculations; scoring semantics live in DomainIntelligenceService.
    """

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._lock = threading.RLock()
        from .migrations import run_migrations

        run_migrations(str(self.db_path))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @staticmethod
    def _dict(row: sqlite3.Row | None) -> dict:
        return dict(row) if row else {}

    def audit(
        self,
        *,
        tenant_id: str,
        session_id: str,
        actor_user_id: str,
        subject_user_id: str,
        entity_type: str,
        entity_id: str,
        action: str,
        before: dict | None = None,
        after: dict | None = None,
        reason: str = "",
        correlation_id: str = "",
        conn: sqlite3.Connection | None = None,
    ) -> dict:
        event_id = f"AUD-{uuid4().hex[:20].upper()}"
        own = conn is None
        conn = conn or self._connect()
        try:
            conn.execute(
                """INSERT INTO domain_audit_events
                (event_id,tenant_id,session_id,actor_user_id,subject_user_id,entity_type,entity_id,action,before_json,after_json,reason,correlation_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event_id,
                    tenant_id,
                    session_id,
                    actor_user_id,
                    subject_user_id,
                    entity_type,
                    entity_id,
                    action,
                    json.dumps(before or {}, ensure_ascii=False),
                    json.dumps(after or {}, ensure_ascii=False),
                    reason,
                    correlation_id,
                ),
            )
            if own:
                conn.commit()
            return {"event_id": event_id, "action": action, "entity_type": entity_type, "entity_id": entity_id}
        finally:
            if own:
                conn.close()

    # ---------- taxonomy / capabilities ----------
    def list_capabilities(self, *, tenant_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM capabilities WHERE status='active' AND tenant_id IN ('global',?)
                ORDER BY CASE WHEN tenant_id=? THEN 0 ELSE 1 END, category,name""",
                (tenant_id, tenant_id),
            ).fetchall()
        out = []
        seen: set[str] = set()
        for row in rows:
            item = dict(row)
            key = item["capability_key"]
            if key in seen:
                continue
            seen.add(key)
            item["aliases"] = json_load(item.pop("aliases_json", "[]"), [])
            item["level_scale"] = json_load(item.pop("level_scale_json", "{}"), {})
            out.append(item)
        return out

    def get_capability(self, capability_id: str, *, tenant_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM capabilities WHERE capability_id=? AND tenant_id IN ('global',?) AND status='active'",
                (capability_id, tenant_id),
            ).fetchone()
        if not row:
            raise KeyError(capability_id)
        item = dict(row)
        item["aliases"] = json_load(item.pop("aliases_json", "[]"), [])
        item["level_scale"] = json_load(item.pop("level_scale_json", "{}"), {})
        return item

    def ensure_custom_capability(
        self, *, tenant_id: str, name: str, category: str = "derived", actor_user_id: str = "system"
    ) -> dict:
        key = norm(name)[:120] or "custom"
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM capabilities WHERE tenant_id=? AND capability_key=? AND status='active'",
                (tenant_id, key),
            ).fetchone()
            if row:
                return self.get_capability(row["capability_id"], tenant_id=tenant_id)
            taxonomy_id = stable_id("TAX", tenant_id, "custom")
            conn.execute(
                """INSERT OR IGNORE INTO capability_taxonomies
                (taxonomy_id,tenant_id,name,description,version,status,created_by)
                VALUES(?,?,?,?,1,'active',?)""",
                (taxonomy_id, tenant_id, "Tenant Custom Capabilities", "Tenant-scoped derived capability taxonomy", actor_user_id),
            )
            capability_id = stable_id("CAP", tenant_id, key)
            aliases = [name]
            conn.execute(
                """INSERT INTO capabilities
                (capability_id,tenant_id,taxonomy_id,capability_key,name,category,description,aliases_json,level_scale_json,version,status,created_by)
                VALUES(?,?,?,?,?,?,?,?,?,1,'active',?)""",
                (
                    capability_id,
                    tenant_id,
                    taxonomy_id,
                    key,
                    name[:160],
                    category[:80],
                    "Derived from a tenant job requirement or evidence label.",
                    json.dumps(aliases, ensure_ascii=False),
                    json.dumps({"min": 0, "max": 100}, ensure_ascii=False),
                    actor_user_id,
                ),
            )
            snapshot = self._dict(conn.execute("SELECT * FROM capabilities WHERE capability_id=?", (capability_id,)).fetchone())
            conn.execute(
                """INSERT INTO capability_versions
                (capability_version_id,tenant_id,capability_id,version,snapshot_json,changed_by,change_reason)
                VALUES(?,?,?,?,?,?,?)""",
                (f"CAPV-{uuid4().hex[:18].upper()}", tenant_id, capability_id, 1, json.dumps(snapshot, ensure_ascii=False), actor_user_id, "derived capability created"),
            )
            self.audit(
                tenant_id=tenant_id,
                session_id="",
                actor_user_id=actor_user_id,
                subject_user_id="",
                entity_type="capability",
                entity_id=capability_id,
                action="created",
                after=snapshot,
                reason="derived from domain mapping",
                conn=conn,
            )
            conn.commit()
        return self.get_capability(capability_id, tenant_id=tenant_id)

    # ---------- claims ----------
    def upsert_claim(
        self,
        *,
        tenant_id: str,
        session_id: str,
        owner_user_id: str,
        source_type: str,
        source_id: str,
        source_locator: str,
        claim_text: str,
        claim_type: str,
        actor_user_id: str,
        reason: str = "synchronized from canonical source",
    ) -> dict:
        claim_text = (claim_text or "").strip()
        if len(claim_text) < 3:
            raise ValueError("claim text is required")
        normalized = norm(claim_text)
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM domain_claims WHERE tenant_id=? AND session_id=? AND source_type=? AND source_id=? AND source_locator=?""",
                (tenant_id, session_id, source_type, source_id, source_locator),
            ).fetchone()
            before = dict(row) if row else {}
            if row:
                claim_id = row["claim_id"]
                actual = int(row["version"] or 1)
                if row["claim_text"] == claim_text and row["status"] == "active" and not row["deleted_at"]:
                    return dict(row)
                version = actual + 1
                conn.execute(
                    """UPDATE domain_claims SET claim_text=?,normalized_text=?,claim_type=?,status='active',version=?,updated_at=CURRENT_TIMESTAMP,deleted_at=NULL
                    WHERE claim_id=?""",
                    (claim_text[:12000], normalized[:12000], claim_type[:80], version, claim_id),
                )
                action = "updated"
            else:
                claim_id = stable_id("CLM", tenant_id, session_id, source_type, source_id, source_locator)
                version = 1
                conn.execute(
                    """INSERT INTO domain_claims
                    (claim_id,tenant_id,session_id,owner_user_id,source_type,source_id,source_locator,claim_text,normalized_text,claim_type,status,version,created_by)
                    VALUES(?,?,?,?,?,?,?,?,?,?, 'active',1,?)""",
                    (claim_id, tenant_id, session_id, owner_user_id, source_type, source_id, source_locator, claim_text[:12000], normalized[:12000], claim_type[:80], actor_user_id),
                )
                action = "created"
            after = self._dict(conn.execute("SELECT * FROM domain_claims WHERE claim_id=?", (claim_id,)).fetchone())
            conn.execute(
                """INSERT OR REPLACE INTO domain_claim_versions
                (claim_version_id,tenant_id,claim_id,version,snapshot_json,changed_by,change_reason)
                VALUES(?,?,?,?,?,?,?)""",
                (stable_id("CLMV", claim_id, str(version)), tenant_id, claim_id, version, json.dumps(after, ensure_ascii=False), actor_user_id, reason),
            )
            self.audit(
                tenant_id=tenant_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                subject_user_id=owner_user_id,
                entity_type="claim",
                entity_id=claim_id,
                action=action,
                before=before,
                after=after,
                reason=reason,
                conn=conn,
            )
            conn.commit()
            return after

    def list_claims(self, *, tenant_id: str, session_id: str, include_deleted: bool = False) -> list[dict]:
        sql = "SELECT * FROM domain_claims WHERE tenant_id=? AND session_id=?"
        params: list[Any] = [tenant_id, session_id]
        if not include_deleted:
            sql += " AND deleted_at IS NULL AND status='active'"
        sql += " ORDER BY updated_at DESC,claim_id"
        with self._connect() as conn:
            return [dict(x) for x in conn.execute(sql, params).fetchall()]

    def get_claim(self, claim_id: str, *, tenant_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM domain_claims WHERE claim_id=? AND tenant_id=?", (claim_id, tenant_id)).fetchone()
        if not row:
            raise KeyError(claim_id)
        return dict(row)

    # ---------- links ----------
    def replace_claim_evidence_links(
        self,
        *,
        tenant_id: str,
        session_id: str,
        claim_id: str,
        links: list[dict],
        actor_user_id: str,
    ) -> list[dict]:
        with self._lock, self._connect() as conn:
            before = [dict(x) for x in conn.execute("SELECT * FROM claim_evidence_links WHERE tenant_id=? AND claim_id=?", (tenant_id, claim_id)).fetchall()]
            conn.execute("DELETE FROM claim_evidence_links WHERE tenant_id=? AND claim_id=?", (tenant_id, claim_id))
            for link in links:
                relation = str(link.get("relation") or "candidate_support")
                evidence_id = str(link.get("evidence_id") or "")
                link_id = stable_id("CEL", tenant_id, claim_id, evidence_id, relation)
                conn.execute(
                    """INSERT INTO claim_evidence_links
                    (link_id,tenant_id,session_id,claim_id,evidence_id,relation,confidence,verification_status,explanation,verifier_type,verified_by,version)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (
                        link_id,
                        tenant_id,
                        session_id,
                        claim_id,
                        evidence_id,
                        relation,
                        float(link.get("confidence") or 0),
                        str(link.get("verification_status") or "UNVERIFIED"),
                        str(link.get("explanation") or "")[:12000],
                        str(link.get("verifier_type") or "deterministic")[:80],
                        str(link.get("verified_by") or "")[:200],
                    ),
                )
            after = [dict(x) for x in conn.execute("SELECT * FROM claim_evidence_links WHERE tenant_id=? AND claim_id=? ORDER BY confidence DESC", (tenant_id, claim_id)).fetchall()]
            self.audit(
                tenant_id=tenant_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                subject_user_id="",
                entity_type="claim_evidence_links",
                entity_id=claim_id,
                action="recomputed",
                before={"items": before},
                after={"items": after},
                reason="claim verification recomputed",
                conn=conn,
            )
            conn.commit()
            return after

    def replace_claim_capability_links(
        self, *, tenant_id: str, claim_id: str, links: list[dict], actor_user_id: str, session_id: str
    ) -> list[dict]:
        with self._lock, self._connect() as conn:
            before = [dict(x) for x in conn.execute("SELECT * FROM claim_capability_links WHERE tenant_id=? AND claim_id=?", (tenant_id, claim_id)).fetchall()]
            conn.execute("DELETE FROM claim_capability_links WHERE tenant_id=? AND claim_id=?", (tenant_id, claim_id))
            for link in links:
                capability_id = str(link["capability_id"])
                relation = str(link.get("relation") or "indicates")
                conn.execute(
                    """INSERT INTO claim_capability_links
                    (link_id,tenant_id,claim_id,capability_id,relation,confidence,explanation,version)
                    VALUES(?,?,?,?,?,?,?,1)""",
                    (
                        stable_id("CCL", tenant_id, claim_id, capability_id, relation),
                        tenant_id,
                        claim_id,
                        capability_id,
                        relation,
                        float(link.get("confidence") or 0),
                        str(link.get("explanation") or "")[:12000],
                    ),
                )
            after = [dict(x) for x in conn.execute("SELECT * FROM claim_capability_links WHERE tenant_id=? AND claim_id=? ORDER BY confidence DESC", (tenant_id, claim_id)).fetchall()]
            self.audit(
                tenant_id=tenant_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                subject_user_id="",
                entity_type="claim_capability_links",
                entity_id=claim_id,
                action="recomputed",
                before={"items": before},
                after={"items": after},
                reason="claim capability mapping recomputed",
                conn=conn,
            )
            conn.commit()
            return after

    def version_requirements(self, *, tenant_id: str, job_id: str, requirements: list[dict], actor_user_id: str, session_id: str) -> list[dict]:
        out=[]
        with self._lock, self._connect() as conn:
            for req in requirements:
                rid=str(req.get("requirement_id") or "")
                if not rid: continue
                current=conn.execute("SELECT * FROM job_requirements WHERE tenant_id=? AND job_id=? AND requirement_id=?",(tenant_id,job_id,rid)).fetchone()
                if not current: continue
                snapshot=dict(current)
                latest=conn.execute("SELECT * FROM job_requirement_versions WHERE tenant_id=? AND requirement_id=? ORDER BY version DESC LIMIT 1",(tenant_id,rid)).fetchone()
                latest_snapshot=json_load(dict(latest).get("snapshot_json","{}"),{}) if latest else {}
                comparable={k:v for k,v in snapshot.items() if k not in {"version","updated_at","created_at"}}
                latest_comparable={k:v for k,v in latest_snapshot.items() if k not in {"version","updated_at","created_at"}}
                if latest and comparable==latest_comparable:
                    out.append({**snapshot,"version":int(dict(latest).get("version") or 1)}); continue
                version=(int(dict(latest).get("version") or 0)+1) if latest else 1
                conn.execute("UPDATE job_requirements SET version=?,updated_at=CURRENT_TIMESTAMP WHERE tenant_id=? AND requirement_id=?",(version,tenant_id,rid))
                snapshot=dict(conn.execute("SELECT * FROM job_requirements WHERE tenant_id=? AND requirement_id=?",(tenant_id,rid)).fetchone())
                conn.execute("""INSERT INTO job_requirement_versions(requirement_version_id,tenant_id,job_id,requirement_id,version,snapshot_json,changed_by,change_reason)
                    VALUES(?,?,?,?,?,?,?,?)""",(stable_id("REQV",rid,str(version)),tenant_id,job_id,rid,version,json.dumps(snapshot,ensure_ascii=False),actor_user_id,"domain recompute snapshot"))
                self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id="",entity_type="job_requirement",entity_id=rid,action="versioned",after=snapshot,reason="domain recompute snapshot",conn=conn)
                out.append(snapshot)
            conn.commit()
        return out

    def requirement_versions(self, requirement_id: str, *, tenant_id: str) -> list[dict]:
        with self._connect() as conn:
            rows=conn.execute("SELECT * FROM job_requirement_versions WHERE tenant_id=? AND requirement_id=? ORDER BY version DESC",(tenant_id,requirement_id)).fetchall()
        out=[]
        for row in rows:
            item=dict(row);item["snapshot"]=json_load(item.pop("snapshot_json","{}"),{});out.append(item)
        return out

    def replace_requirement_capability_links(
        self,
        *,
        tenant_id: str,
        job_id: str,
        requirement_id: str,
        links: list[dict],
        actor_user_id: str,
        session_id: str,
    ) -> list[dict]:
        with self._lock, self._connect() as conn:
            before = [dict(x) for x in conn.execute("SELECT * FROM job_requirement_capability_links WHERE tenant_id=? AND requirement_id=?", (tenant_id, requirement_id)).fetchall()]
            conn.execute("DELETE FROM job_requirement_capability_links WHERE tenant_id=? AND requirement_id=?", (tenant_id, requirement_id))
            for link in links:
                capability_id = str(link["capability_id"])
                conn.execute(
                    """INSERT INTO job_requirement_capability_links
                    (link_id,tenant_id,job_id,requirement_id,capability_id,weight,minimum_score,mapping_status,explanation,version)
                    VALUES(?,?,?,?,?,?,?,?,?,1)""",
                    (
                        stable_id("RCL", tenant_id, requirement_id, capability_id),
                        tenant_id,
                        job_id,
                        requirement_id,
                        capability_id,
                        float(link.get("weight") or 1),
                        float(link.get("minimum_score") or 60),
                        str(link.get("mapping_status") or "derived")[:80],
                        str(link.get("explanation") or "")[:12000],
                    ),
                )
            after = [dict(x) for x in conn.execute("SELECT * FROM job_requirement_capability_links WHERE tenant_id=? AND requirement_id=? ORDER BY weight DESC", (tenant_id, requirement_id)).fetchall()]
            self.audit(
                tenant_id=tenant_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                subject_user_id="",
                entity_type="requirement_capability_links",
                entity_id=requirement_id,
                action="recomputed",
                before={"items": before},
                after={"items": after},
                reason="job requirement capability mapping recomputed",
                conn=conn,
            )
            conn.commit()
            return after

    # ---------- assessments / gaps ----------
    def save_assessment(
        self,
        *,
        tenant_id: str,
        session_id: str,
        owner_user_id: str,
        capability_id: str,
        potential_score: float,
        verified_score: float,
        confidence: float,
        explanation: dict,
        contributions: list[dict],
        actor_user_id: str,
    ) -> dict:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT COALESCE(MAX(assessment_version),0) v FROM capability_assessments WHERE tenant_id=? AND session_id=? AND capability_id=?",
                (tenant_id, session_id, capability_id),
            ).fetchone()
            version = int(row["v"] or 0) + 1
            assessment_id = stable_id("ASM", tenant_id, session_id, capability_id, str(version))
            conn.execute(
                """INSERT INTO capability_assessments
                (assessment_id,tenant_id,session_id,owner_user_id,capability_id,assessment_version,potential_score,verified_score,confidence,methodology_version,explanation_json,created_by)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    assessment_id,
                    tenant_id,
                    session_id,
                    owner_user_id,
                    capability_id,
                    version,
                    round(float(potential_score), 3),
                    round(float(verified_score), 3),
                    round(float(confidence), 4),
                    METHODOLOGY_VERSION,
                    json.dumps(explanation, ensure_ascii=False),
                    actor_user_id,
                ),
            )
            for c in contributions:
                conn.execute(
                    """INSERT INTO capability_assessment_evidence
                    (link_id,tenant_id,assessment_id,capability_id,claim_id,evidence_id,contribution_type,potential_weight,verified_weight,explanation)
                    VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        f"ASE-{uuid4().hex[:18].upper()}",
                        tenant_id,
                        assessment_id,
                        capability_id,
                        str(c.get("claim_id") or ""),
                        str(c.get("evidence_id") or ""),
                        str(c.get("contribution_type") or "candidate"),
                        float(c.get("potential_weight") or 0),
                        float(c.get("verified_weight") or 0),
                        str(c.get("explanation") or "")[:12000],
                    ),
                )
            result = self._dict(conn.execute("SELECT * FROM capability_assessments WHERE assessment_id=?", (assessment_id,)).fetchone())
            self.audit(
                tenant_id=tenant_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                subject_user_id=owner_user_id,
                entity_type="capability_assessment",
                entity_id=assessment_id,
                action="calculated",
                after=result,
                reason=METHODOLOGY_VERSION,
                conn=conn,
            )
            conn.commit()
        result["explanation"] = json_load(result.pop("explanation_json", "{}"), {})
        result["contributions"] = contributions
        return result

    def latest_assessments(self, *, tenant_id: str, session_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT a.*,c.name capability_name,c.capability_key,c.category
                FROM capability_assessments a
                JOIN capabilities c ON c.capability_id=a.capability_id
                JOIN (SELECT capability_id,MAX(assessment_version) v FROM capability_assessments
                      WHERE tenant_id=? AND session_id=? GROUP BY capability_id) latest
                  ON latest.capability_id=a.capability_id AND latest.v=a.assessment_version
                WHERE a.tenant_id=? AND a.session_id=? ORDER BY a.verified_score DESC,a.potential_score DESC,c.name""",
                (tenant_id, session_id, tenant_id, session_id),
            ).fetchall()
            out = []
            for row in rows:
                item = dict(row)
                item["explanation"] = json_load(item.pop("explanation_json", "{}"), {})
                item["contributions"] = [dict(x) for x in conn.execute(
                    "SELECT * FROM capability_assessment_evidence WHERE tenant_id=? AND assessment_id=? ORDER BY verified_weight DESC,potential_weight DESC",
                    (tenant_id, item["assessment_id"]),
                ).fetchall()]
                out.append(item)
            return out

    def upsert_gap(
        self,
        *,
        tenant_id: str,
        session_id: str,
        owner_user_id: str,
        job_id: str,
        requirement_id: str,
        capability_id: str,
        gap_type: str,
        severity: float,
        potential_score: float,
        verified_score: float,
        required_score: float,
        explanation: dict,
        actor_user_id: str,
    ) -> dict:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """SELECT * FROM career_gaps WHERE tenant_id=? AND session_id=? AND job_id=? AND requirement_id=? AND capability_id=?""",
                (tenant_id, session_id, job_id, requirement_id, capability_id),
            ).fetchone()
            before = dict(row) if row else {}
            if row:
                gap_id = row["gap_id"]
                version = int(row["version"] or 1) + 1
                conn.execute(
                    """UPDATE career_gaps SET gap_type=?,severity=?,status='open',version=?,potential_score=?,verified_score=?,required_score=?,explanation_json=?,updated_at=CURRENT_TIMESTAMP,deleted_at=NULL
                    WHERE gap_id=?""",
                    (gap_type, severity, version, potential_score, verified_score, required_score, json.dumps(explanation, ensure_ascii=False), gap_id),
                )
            else:
                gap_id = stable_id("GAP", tenant_id, session_id, job_id, requirement_id, capability_id)
                version = 1
                conn.execute(
                    """INSERT INTO career_gaps
                    (gap_id,tenant_id,session_id,owner_user_id,job_id,requirement_id,capability_id,gap_type,severity,status,version,potential_score,verified_score,required_score,explanation_json,created_by)
                    VALUES(?,?,?,?,?,?,?,?,?,'open',1,?,?,?,?,?)""",
                    (
                        gap_id,
                        tenant_id,
                        session_id,
                        owner_user_id,
                        job_id,
                        requirement_id,
                        capability_id,
                        gap_type,
                        round(severity, 3),
                        round(potential_score, 3),
                        round(verified_score, 3),
                        round(required_score, 3),
                        json.dumps(explanation, ensure_ascii=False),
                        actor_user_id,
                    ),
                )
            after = self._dict(conn.execute("SELECT * FROM career_gaps WHERE gap_id=?", (gap_id,)).fetchone())
            conn.execute(
                """INSERT OR REPLACE INTO career_gap_versions
                (gap_version_id,tenant_id,gap_id,version,snapshot_json,changed_by,change_reason)
                VALUES(?,?,?,?,?,?,?)""",
                (stable_id("GAPV", gap_id, str(version)), tenant_id, gap_id, version, json.dumps(after, ensure_ascii=False), actor_user_id, "domain recompute"),
            )
            self.audit(
                tenant_id=tenant_id,
                session_id=session_id,
                actor_user_id=actor_user_id,
                subject_user_id=owner_user_id,
                entity_type="gap",
                entity_id=gap_id,
                action="updated" if before else "created",
                before=before,
                after=after,
                reason="requirement/capability comparison",
                conn=conn,
            )
            conn.commit()
        after["explanation"] = json_load(after.pop("explanation_json", "{}"), {})
        return after

    def list_gaps(self, *, tenant_id: str, session_id: str, job_id: str = "") -> list[dict]:
        sql = """SELECT g.*,r.requirement_text,r.category requirement_category,c.name capability_name,c.capability_key
                 FROM career_gaps g JOIN job_requirements r ON r.requirement_id=g.requirement_id
                 LEFT JOIN capabilities c ON c.capability_id=g.capability_id
                 WHERE g.tenant_id=? AND g.session_id=? AND g.deleted_at IS NULL"""
        params: list[Any] = [tenant_id, session_id]
        if job_id:
            sql += " AND g.job_id=?"
            params.append(job_id)
        sql += " ORDER BY g.severity DESC,g.updated_at DESC"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["explanation"] = json_load(item.pop("explanation_json", "{}"), {})
            out.append(item)
        return out

    # ---------- explain / audit ----------
    def explain_capability(self, capability_id: str, *, tenant_id: str, session_id: str) -> dict:
        capability = self.get_capability(capability_id, tenant_id=tenant_id)
        assessments = [x for x in self.latest_assessments(tenant_id=tenant_id, session_id=session_id) if x["capability_id"] == capability_id]
        with self._connect() as conn:
            claims = [dict(x) for x in conn.execute(
                """SELECT c.*,l.relation,l.confidence link_confidence,l.explanation link_explanation
                FROM claim_capability_links l JOIN domain_claims c ON c.claim_id=l.claim_id
                WHERE l.tenant_id=? AND l.capability_id=? AND c.session_id=? AND c.deleted_at IS NULL
                ORDER BY l.confidence DESC""",
                (tenant_id, capability_id, session_id),
            ).fetchall()]
            for claim in claims:
                claim["evidence_links"] = [dict(x) for x in conn.execute(
                    "SELECT * FROM claim_evidence_links WHERE tenant_id=? AND claim_id=? ORDER BY confidence DESC",
                    (tenant_id, claim["claim_id"]),
                ).fetchall()]
        return {"capability": capability, "latest_assessment": assessments[0] if assessments else None, "claims": claims, "methodology_version": METHODOLOGY_VERSION}

    def audit_events(
        self, *, tenant_id: str, session_id: str = "", entity_type: str = "", entity_id: str = "", limit: int = 200
    ) -> list[dict]:
        sql = "SELECT * FROM domain_audit_events WHERE tenant_id=?"
        params: list[Any] = [tenant_id]
        if session_id:
            sql += " AND session_id=?"
            params.append(session_id)
        if entity_type:
            sql += " AND entity_type=?"
            params.append(entity_type)
        if entity_id:
            sql += " AND entity_id=?"
            params.append(entity_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(max(1, min(limit, 1000)))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        out = []
        for row in rows:
            item = dict(row)
            item["before"] = json_load(item.pop("before_json", "{}"), {})
            item["after"] = json_load(item.pop("after_json", "{}"), {})
            out.append(item)
        return out


    def claim_capability_links_for_session(self, *, tenant_id: str, session_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""SELECT l.* FROM claim_capability_links l JOIN domain_claims c ON c.claim_id=l.claim_id
                WHERE l.tenant_id=? AND c.tenant_id=? AND c.session_id=? AND c.deleted_at IS NULL""",
                (tenant_id, tenant_id, session_id)).fetchall()
        return [dict(x) for x in rows]

    def claim_evidence_links_for_session(self, *, tenant_id: str, session_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""SELECT l.* FROM claim_evidence_links l JOIN domain_claims c ON c.claim_id=l.claim_id
                WHERE l.tenant_id=? AND c.tenant_id=? AND c.session_id=? AND c.deleted_at IS NULL""",
                (tenant_id, tenant_id, session_id)).fetchall()
        return [dict(x) for x in rows]

    def requirement_links_for_job(self, *, tenant_id: str, job_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM job_requirement_capability_links WHERE tenant_id=? AND job_id=? ORDER BY requirement_id,weight DESC",
                (tenant_id, job_id)).fetchall()
        return [dict(x) for x in rows]


    def update_claim(
        self, *, tenant_id: str, session_id: str, owner_user_id: str, claim_id: str,
        claim_text: str, claim_type: str, actor_user_id: str, expected_version: int | None = None, reason: str = "manual claim edit"
    ) -> dict:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM domain_claims WHERE claim_id=? AND tenant_id=? AND session_id=? AND owner_user_id=? AND deleted_at IS NULL",
                (claim_id, tenant_id, session_id, owner_user_id),
            ).fetchone()
            if not row:
                raise KeyError(claim_id)
            before = dict(row); actual = int(before.get("version") or 1)
            if expected_version is not None and expected_version != actual:
                raise DomainVersionConflict(claim_id, expected_version, actual)
            next_version = actual + 1
            conn.execute(
                "UPDATE domain_claims SET claim_text=?,normalized_text=?,claim_type=?,version=?,updated_at=CURRENT_TIMESTAMP WHERE claim_id=?",
                ((claim_text or "").strip()[:12000], norm(claim_text)[:12000], claim_type[:80], next_version, claim_id),
            )
            after = self._dict(conn.execute("SELECT * FROM domain_claims WHERE claim_id=?", (claim_id,)).fetchone())
            conn.execute(
                """INSERT INTO domain_claim_versions(claim_version_id,tenant_id,claim_id,version,snapshot_json,changed_by,change_reason)
                VALUES(?,?,?,?,?,?,?)""",
                (stable_id("CLMV", claim_id, str(next_version)), tenant_id, claim_id, next_version, json.dumps(after, ensure_ascii=False), actor_user_id, reason),
            )
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id=owner_user_id,
                       entity_type="claim",entity_id=claim_id,action="updated",before=before,after=after,reason=reason,conn=conn)
            conn.commit(); return after

    def claim_versions(self, claim_id: str, *, tenant_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM domain_claim_versions WHERE tenant_id=? AND claim_id=? ORDER BY version DESC",
                (tenant_id, claim_id),
            ).fetchall()
        out=[]
        for row in rows:
            item=dict(row); item["snapshot"]=json_load(item.pop("snapshot_json","{}"),{}); out.append(item)
        return out

    def requirement_mappings(self, *, tenant_id: str, job_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT l.*,r.requirement_text,r.category requirement_category,r.importance,c.name capability_name,c.capability_key
                FROM job_requirement_capability_links l
                JOIN job_requirements r ON r.requirement_id=l.requirement_id
                JOIN capabilities c ON c.capability_id=l.capability_id
                WHERE l.tenant_id=? AND l.job_id=? ORDER BY r.importance DESC,l.weight DESC""",
                (tenant_id, job_id),
            ).fetchall()
        return [dict(x) for x in rows]

    def assessment_versions(self, capability_id: str, *, tenant_id: str, session_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM capability_assessments WHERE tenant_id=? AND session_id=? AND capability_id=?
                ORDER BY assessment_version DESC""",
                (tenant_id, session_id, capability_id),
            ).fetchall()
        out=[]
        for row in rows:
            item=dict(row); item["explanation"]=json_load(item.pop("explanation_json","{}"),{}); out.append(item)
        return out

    def gap_versions(self, gap_id: str, *, tenant_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM career_gap_versions WHERE tenant_id=? AND gap_id=? ORDER BY version DESC",
                (tenant_id, gap_id),
            ).fetchall()
        out=[]
        for row in rows:
            item=dict(row); item["snapshot"]=json_load(item.pop("snapshot_json","{}"),{}); out.append(item)
        return out

    def update_gap_status(
        self, *, tenant_id: str, session_id: str, owner_user_id: str, gap_id: str, status: str,
        actor_user_id: str, expected_version: int | None = None, reason: str = "gap status update"
    ) -> dict:
        allowed={"open","planned","in_progress","resolved","accepted","dismissed"}
        if status not in allowed:
            raise ValueError("invalid gap status")
        with self._lock, self._connect() as conn:
            row=conn.execute(
                "SELECT * FROM career_gaps WHERE gap_id=? AND tenant_id=? AND session_id=? AND owner_user_id=? AND deleted_at IS NULL",
                (gap_id,tenant_id,session_id,owner_user_id),
            ).fetchone()
            if not row: raise KeyError(gap_id)
            before=dict(row); actual=int(before.get("version") or 1)
            if expected_version is not None and expected_version != actual:
                raise DomainVersionConflict(gap_id,expected_version,actual)
            version=actual+1
            conn.execute("UPDATE career_gaps SET status=?,version=?,updated_at=CURRENT_TIMESTAMP WHERE gap_id=?",(status,version,gap_id))
            after=self._dict(conn.execute("SELECT * FROM career_gaps WHERE gap_id=?",(gap_id,)).fetchone())
            conn.execute(
                """INSERT INTO career_gap_versions(gap_version_id,tenant_id,gap_id,version,snapshot_json,changed_by,change_reason)
                VALUES(?,?,?,?,?,?,?)""",
                (stable_id("GAPV",gap_id,str(version)),tenant_id,gap_id,version,json.dumps(after,ensure_ascii=False),actor_user_id,reason),
            )
            self.audit(tenant_id=tenant_id,session_id=session_id,actor_user_id=actor_user_id,subject_user_id=owner_user_id,
                       entity_type="gap",entity_id=gap_id,action="status_changed",before=before,after=after,reason=reason,conn=conn)
            conn.commit()
        after["explanation"]=json_load(after.pop("explanation_json","{}"),{}); return after



@dataclass
class RecomputeResult:
    claims: list[dict]
    claim_evidence_links: list[dict]
    claim_capability_links: list[dict]
    requirement_capability_links: list[dict]
    assessments: list[dict]
    gaps: list[dict]
    explanation: dict


class DomainIntelligenceService:
    """Server-authoritative Claim → Capability → Requirement → Gap engine.

    v1.5 scores are transparent deterministic indicators, not psychometric measurements. Every
    assessment stores its methodology version and contribution-level explanation so later calibrated
    models can coexist without rewriting historical results.
    """

    def __init__(self, store: Any, verifier: EvidenceVerificationService, job_intelligence: Any):
        self.store = store
        self.verifier = verifier
        self.job_intelligence = job_intelligence

    @staticmethod
    def _claim_sentences(text: str) -> list[str]:
        parts = [x.strip(" -•\t") for x in re.split(r"(?<=[。！？!?；;])|\n+", text or "")]
        return [x for x in parts if 8 <= len(x) <= 1200][:200]

    @staticmethod
    def _evidence_trust(item: dict) -> tuple[str, float]:
        status = str(item.get("verification_status") or ("VERIFIED" if item.get("verified") else "SELF_REPORTED")).upper()
        return status, float(TRUST_WEIGHTS.get(status, 0.25))

    def sync_claims(
        self,
        *,
        tenant_id: str,
        session_id: str,
        owner_user_id: str,
        evidence_items: list[dict],
        artifact_items: list[dict],
        actor_user_id: str,
    ) -> list[dict]:
        for ev in evidence_items:
            content = str(ev.get("content") or "")
            label = str(ev.get("source_label") or "Evidence")
            if content.strip():
                self.store.upsert_claim(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    owner_user_id=owner_user_id,
                    source_type="evidence",
                    source_id=str(ev.get("evidence_id") or ""),
                    source_locator="0",
                    claim_text=f"{label}: {content}",
                    claim_type="experience",
                    actor_user_id=actor_user_id,
                    reason="claim synchronized from canonical evidence",
                )
        for artifact in artifact_items:
            source_id = str(artifact.get("version_id") or artifact.get("artifact_id") or "")
            content = str(artifact.get("content") or "")
            for idx, sentence in enumerate(self._claim_sentences(content)):
                self.store.upsert_claim(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    owner_user_id=owner_user_id,
                    source_type="artifact",
                    source_id=source_id,
                    source_locator=str(idx),
                    claim_text=sentence,
                    claim_type="artifact_claim",
                    actor_user_id=actor_user_id,
                    reason="claim synchronized from current artifact version",
                )
        return self.store.list_claims(tenant_id=tenant_id, session_id=session_id)

    def verify_claims(
        self,
        *,
        tenant_id: str,
        session_id: str,
        claims: list[dict],
        evidence_items: list[dict],
        actor_user_id: str,
    ) -> list[dict]:
        all_links: list[dict] = []
        for claim in claims:
            result = self.verifier.verify(claim["claim_text"], evidence_items)
            candidates = result.candidates or []
            links: list[dict] = []
            for candidate in candidates[:5]:
                evidence_id = str(candidate.get("evidence_id") or "")
                evidence = next((x for x in evidence_items if str(x.get("evidence_id")) == evidence_id), {})
                trust_status, trust_weight = self._evidence_trust(evidence)
                relation = "candidate_support"
                verification_status = result.status
                if result.status == STATUS_CONTRADICTED:
                    relation = "contradicts"
                elif result.status == STATUS_SUPPORTED and trust_status in VERIFIED_STATES:
                    relation = "verified_support"
                elif result.status in {STATUS_SUPPORTED, STATUS_PARTIAL} and trust_status in PARTIAL_TRUST_STATES:
                    relation = "partial_support"
                elif result.status == STATUS_UNSUPPORTED:
                    relation = "unsupported"
                confidence = float(candidate.get("score") or result.confidence or 0) * max(0.1, abs(trust_weight))
                links.append(
                    {
                        "evidence_id": evidence_id,
                        "relation": relation,
                        "confidence": min(0.999, max(0.0, confidence)),
                        "verification_status": verification_status,
                        "explanation": f"{result.reason}; evidence trust={trust_status}",
                        "verifier_type": "deterministic-v1.5",
                        "verified_by": str(evidence.get("verified_by") or ""),
                    }
                )
            if not links and result.best_evidence_id:
                links.append(
                    {
                        "evidence_id": result.best_evidence_id,
                        "relation": "candidate_support",
                        "confidence": result.confidence,
                        "verification_status": result.status,
                        "explanation": result.reason,
                        "verifier_type": "deterministic-v1.5",
                    }
                )
            persisted = self.store.replace_claim_evidence_links(
                tenant_id=tenant_id,
                session_id=session_id,
                claim_id=claim["claim_id"],
                links=links,
                actor_user_id=actor_user_id,
            )
            all_links.extend(persisted)
        return all_links

    def _match_capabilities(self, text: str, capabilities: list[dict]) -> list[tuple[dict, float, str]]:
        out: list[tuple[dict, float, str]] = []
        text_norm = norm(text)
        for cap in capabilities:
            aliases = [cap.get("name", ""), cap.get("capability_key", "")] + list(cap.get("aliases") or [])
            best = 0.0
            matched = ""
            for alias in aliases:
                alias_norm = norm(str(alias))
                if not alias_norm:
                    continue
                score = 0.96 if alias_norm in text_norm else overlap(text, str(alias))
                if score > best:
                    best, matched = score, str(alias)
            if best >= 0.28:
                out.append((cap, min(0.99, best), matched))
        return sorted(out, key=lambda x: x[1], reverse=True)

    def map_claims_to_capabilities(
        self,
        *,
        tenant_id: str,
        session_id: str,
        claims: list[dict],
        actor_user_id: str,
    ) -> list[dict]:
        capabilities = self.store.list_capabilities(tenant_id=tenant_id)
        all_links: list[dict] = []
        for claim in claims:
            matches = self._match_capabilities(claim["claim_text"], capabilities)[:6]
            links = [
                {
                    "capability_id": cap["capability_id"],
                    "relation": "indicates",
                    "confidence": score,
                    "explanation": f"claim contains or semantically overlaps capability alias '{alias}'",
                }
                for cap, score, alias in matches
            ]
            persisted = self.store.replace_claim_capability_links(
                tenant_id=tenant_id,
                claim_id=claim["claim_id"],
                links=links,
                actor_user_id=actor_user_id,
                session_id=session_id,
            )
            all_links.extend(persisted)
        return all_links

    def map_requirements_to_capabilities(
        self,
        *,
        tenant_id: str,
        session_id: str,
        job_id: str,
        requirements: list[dict],
        actor_user_id: str,
    ) -> list[dict]:
        capabilities = self.store.list_capabilities(tenant_id=tenant_id)
        all_links: list[dict] = []
        for req in requirements:
            text = str(req.get("requirement_text") or req.get("text") or "")
            matches = self._match_capabilities(text, capabilities)[:3]
            if not matches:
                custom = self.store.ensure_custom_capability(
                    tenant_id=tenant_id,
                    name=text[:120] or "Unmapped requirement",
                    category=str(req.get("category") or "requirement"),
                    actor_user_id=actor_user_id,
                )
                capabilities.append(custom)
                matches = [(custom, 0.55, text[:120])]
            importance = max(1, min(int(req.get("importance") or 3), 5))
            links = [
                {
                    "capability_id": cap["capability_id"],
                    "weight": round(score, 4),
                    "minimum_score": 45 + importance * 10,
                    "mapping_status": "derived",
                    "explanation": f"requirement mapped through alias/overlap '{alias}'; importance={importance}",
                }
                for cap, score, alias in matches
            ]
            persisted = self.store.replace_requirement_capability_links(
                tenant_id=tenant_id,
                job_id=job_id,
                requirement_id=str(req.get("requirement_id") or ""),
                links=links,
                actor_user_id=actor_user_id,
                session_id=session_id,
            )
            all_links.extend(persisted)
        return all_links

    @staticmethod
    def _score_from_weight(weight: float) -> float:
        # Saturating and monotonic: 0 contribution -> 0; diversified contributions approach 100.
        return round(100.0 * (1.0 - math.exp(-max(0.0, weight) / 1.6)), 2)

    def assess_capabilities(
        self,
        *,
        tenant_id: str,
        session_id: str,
        owner_user_id: str,
        claims: list[dict],
        evidence_items: list[dict],
        actor_user_id: str,
    ) -> list[dict]:
        capabilities = self.store.list_capabilities(tenant_id=tenant_id)
        claim_by_id = {x["claim_id"]: x for x in claims}
        evidence_by_id = {str(x.get("evidence_id")): x for x in evidence_items}
        ccl = self.store.claim_capability_links_for_session(tenant_id=tenant_id, session_id=session_id)
        cel = self.store.claim_evidence_links_for_session(tenant_id=tenant_id, session_id=session_id)
        evidence_links_by_claim: dict[str, list[dict]] = {}
        for link in cel:
            evidence_links_by_claim.setdefault(link["claim_id"], []).append(link)
        claim_links_by_capability: dict[str, list[dict]] = {}
        for link in ccl:
            claim_links_by_capability.setdefault(link["capability_id"], []).append(link)

        assessments = []
        for cap in capabilities:
            contribution_rows: list[dict] = []
            potential_weight = 0.0
            verified_weight = 0.0
            source_ids: set[str] = set()
            verified_sources: set[str] = set()
            for claim_link in claim_links_by_capability.get(cap["capability_id"], []):
                claim_id = claim_link["claim_id"]
                claim = claim_by_id.get(claim_id, {})
                capability_confidence = float(claim_link.get("confidence") or 0)
                evidence_links = evidence_links_by_claim.get(claim_id, [])
                if not evidence_links:
                    w = 0.18 * capability_confidence
                    potential_weight += w
                    contribution_rows.append(
                        {
                            "claim_id": claim_id,
                            "evidence_id": "",
                            "contribution_type": "unlinked_claim",
                            "potential_weight": w,
                            "verified_weight": 0,
                            "explanation": "claim indicates capability but has no linked evidence",
                        }
                    )
                for ev_link in evidence_links:
                    evidence_id = str(ev_link.get("evidence_id") or "")
                    ev = evidence_by_id.get(evidence_id, {})
                    trust_status, trust_weight = self._evidence_trust(ev)
                    relation = str(ev_link.get("relation") or "candidate_support")
                    relation_weight = {
                        "verified_support": 1.0,
                        "partial_support": 0.65,
                        "candidate_support": 0.35,
                        "unsupported": 0.0,
                        "contradicts": -0.8,
                    }.get(relation, 0.25)
                    link_confidence = float(ev_link.get("confidence") or 0)
                    potential = capability_confidence * max(0.0, relation_weight) * max(0.2, abs(trust_weight)) * max(0.25, link_confidence)
                    verified = capability_confidence * max(0.0, relation_weight) * max(0.0, trust_weight) * max(0.25, link_confidence)
                    if relation == "contradicts" or trust_weight < 0:
                        potential = -0.35 * capability_confidence
                        verified = -0.55 * capability_confidence
                    potential_weight += potential
                    verified_weight += verified
                    if evidence_id:
                        source_ids.add(evidence_id)
                        if trust_status in VERIFIED_STATES:
                            verified_sources.add(evidence_id)
                    contribution_rows.append(
                        {
                            "claim_id": claim_id,
                            "evidence_id": evidence_id,
                            "contribution_type": relation,
                            "potential_weight": round(potential, 4),
                            "verified_weight": round(verified, 4),
                            "explanation": f"claim-capability={capability_confidence:.2f}; relation={relation}; trust={trust_status}; link={link_confidence:.2f}",
                        }
                    )
            potential_score = self._score_from_weight(potential_weight)
            verified_score = self._score_from_weight(verified_weight)
            diversity = min(1.0, len(source_ids) / 3.0)
            verification_ratio = len(verified_sources) / max(1, len(source_ids))
            confidence = round(min(0.98, 0.25 + diversity * 0.35 + verification_ratio * 0.3 + min(0.08, len(contribution_rows) * 0.015)), 4)
            explanation = {
                "methodology": METHODOLOGY_VERSION,
                "warning": "Deterministic explainable indicator; not a psychometric or validated proficiency test.",
                "potential_weight": round(potential_weight, 4),
                "verified_weight": round(verified_weight, 4),
                "source_count": len(source_ids),
                "verified_source_count": len(verified_sources),
                "claim_count": len({x["claim_id"] for x in contribution_rows if x.get("claim_id")}),
                "formula": "score = 100 * (1 - exp(-max(weight,0)/1.6))",
            }
            assessments.append(
                self.store.save_assessment(
                    tenant_id=tenant_id,
                    session_id=session_id,
                    owner_user_id=owner_user_id,
                    capability_id=cap["capability_id"],
                    potential_score=potential_score,
                    verified_score=verified_score,
                    confidence=confidence,
                    explanation=explanation,
                    contributions=contribution_rows,
                    actor_user_id=actor_user_id,
                )
            )
        return assessments

    def calculate_gaps(
        self,
        *,
        tenant_id: str,
        session_id: str,
        owner_user_id: str,
        job_id: str,
        requirements: list[dict],
        assessments: list[dict],
        actor_user_id: str,
    ) -> list[dict]:
        assessments_by_cap = {x["capability_id"]: x for x in assessments}
        mappings = self.store.requirement_links_for_job(tenant_id=tenant_id, job_id=job_id)
        by_req: dict[str, list[dict]] = {}
        for m in mappings:
            by_req.setdefault(m["requirement_id"], []).append(m)
        gaps = []
        for req in requirements:
            requirement_id = str(req.get("requirement_id") or "")
            req_maps = by_req.get(requirement_id, [])
            for mapping in req_maps or [{"capability_id": "", "minimum_score": 60, "weight": 1.0, "explanation": "unmapped requirement"}]:
                capability_id = str(mapping.get("capability_id") or "")
                assessment = assessments_by_cap.get(capability_id, {})
                potential = float(assessment.get("potential_score") or 0)
                verified = float(assessment.get("verified_score") or 0)
                required = float(mapping.get("minimum_score") or 60)
                if not assessment or potential < 10:
                    gap_type = "NO_CAPABILITY"
                elif potential < required:
                    gap_type = "LOW_CAPABILITY"
                elif verified < 10:
                    gap_type = "NO_VERIFIED_EVIDENCE"
                elif verified < required:
                    gap_type = "PARTIAL_EVIDENCE"
                else:
                    gap_type = "COVERED"
                severity = max(0.0, required - verified) * max(0.25, float(mapping.get("weight") or 1))
                explanation = {
                    "requirement": str(req.get("requirement_text") or req.get("text") or ""),
                    "importance": int(req.get("importance") or 3),
                    "mapping_explanation": mapping.get("explanation", ""),
                    "potential_score": potential,
                    "verified_score": verified,
                    "required_score": required,
                    "decision": gap_type,
                    "recommended_action": {
                        "NO_CAPABILITY": "Build the capability through a targeted learning/project plan.",
                        "LOW_CAPABILITY": "Complete a higher-complexity supervised project and record outcomes.",
                        "NO_VERIFIED_EVIDENCE": "Attach and submit explicit proof for review.",
                        "PARTIAL_EVIDENCE": "Strengthen evidence coverage or obtain authorized verification.",
                        "COVERED": "Maintain current evidence and update it when stale.",
                    }[gap_type],
                }
                gaps.append(
                    self.store.upsert_gap(
                        tenant_id=tenant_id,
                        session_id=session_id,
                        owner_user_id=owner_user_id,
                        job_id=job_id,
                        requirement_id=requirement_id,
                        capability_id=capability_id,
                        gap_type=gap_type,
                        severity=severity,
                        potential_score=potential,
                        verified_score=verified,
                        required_score=required,
                        explanation=explanation,
                        actor_user_id=actor_user_id,
                    )
                )
        return gaps

    def recompute(
        self,
        *,
        tenant_id: str,
        session_id: str,
        owner_user_id: str,
        actor_user_id: str,
        job_id: str,
        evidence_items: list[dict],
        artifact_items: list[dict],
    ) -> RecomputeResult:
        claims = self.sync_claims(
            tenant_id=tenant_id,
            session_id=session_id,
            owner_user_id=owner_user_id,
            evidence_items=evidence_items,
            artifact_items=artifact_items,
            actor_user_id=actor_user_id,
        )
        cel = self.verify_claims(
            tenant_id=tenant_id,
            session_id=session_id,
            claims=claims,
            evidence_items=evidence_items,
            actor_user_id=actor_user_id,
        )
        ccl = self.map_claims_to_capabilities(
            tenant_id=tenant_id,
            session_id=session_id,
            claims=claims,
            actor_user_id=actor_user_id,
        )
        requirements = self.job_intelligence.ensure_requirements(job_id, tenant_id=tenant_id) if job_id else []
        if job_id:
            requirements = self.store.version_requirements(tenant_id=tenant_id, job_id=job_id, requirements=requirements, actor_user_id=actor_user_id, session_id=session_id)
        rcl = self.map_requirements_to_capabilities(
            tenant_id=tenant_id,
            session_id=session_id,
            job_id=job_id,
            requirements=requirements,
            actor_user_id=actor_user_id,
        ) if job_id else []
        assessments = self.assess_capabilities(
            tenant_id=tenant_id,
            session_id=session_id,
            owner_user_id=owner_user_id,
            claims=claims,
            evidence_items=evidence_items,
            actor_user_id=actor_user_id,
        )
        gaps = self.calculate_gaps(
            tenant_id=tenant_id,
            session_id=session_id,
            owner_user_id=owner_user_id,
            job_id=job_id,
            requirements=requirements,
            assessments=assessments,
            actor_user_id=actor_user_id,
        ) if job_id else []
        return RecomputeResult(
            claims=claims,
            claim_evidence_links=cel,
            claim_capability_links=ccl,
            requirement_capability_links=rcl,
            assessments=assessments,
            gaps=gaps,
            explanation={
                "methodology_version": METHODOLOGY_VERSION,
                "claim_count": len(claims),
                "capability_count": len(assessments),
                "gap_count": len([x for x in gaps if x.get("gap_type") != "COVERED"]),
                "principle": "Claims, capabilities, requirements and gaps are stored as independent versioned entities; every score is traceable to contribution rows.",
            },
        )

    def snapshot(self, *, tenant_id: str, session_id: str, job_id: str = "") -> dict:
        assessments = self.store.latest_assessments(tenant_id=tenant_id, session_id=session_id)
        gaps = self.store.list_gaps(tenant_id=tenant_id, session_id=session_id, job_id=job_id)
        claims = self.store.list_claims(tenant_id=tenant_id, session_id=session_id)
        potential_scores = [float(x.get("potential_score") or 0) for x in assessments]
        verified_scores = [float(x.get("verified_score") or 0) for x in assessments]
        requirements = self.store.requirement_mappings(tenant_id=tenant_id, job_id=job_id) if job_id else []
        audit = self.store.audit_events(tenant_id=tenant_id, session_id=session_id, limit=200)
        return {
            "claims": claims,
            "capabilities": assessments,
            "requirements": requirements,
            "gaps": gaps,
            "audit": audit,
            "summary": {
                "methodology_version": METHODOLOGY_VERSION,
                "claim_count": len(claims),
                "capability_count": len(assessments),
                "open_gap_count": len([x for x in gaps if x.get("gap_type") != "COVERED"]),
                "potential_match": round(sum(potential_scores) / max(1, len(potential_scores)), 1),
                "verified_match": round(sum(verified_scores) / max(1, len(verified_scores)), 1),
                "evidence_coverage": round(
                    100 * sum(1 for x in assessments if float(x.get("verified_score") or 0) > 0) / max(1, len(assessments)), 1
                ),
            },
        }
