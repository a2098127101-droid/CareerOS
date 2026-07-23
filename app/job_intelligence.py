from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import uuid4

from .domain.profile import ParticipantProfile

MATCHED = "MATCHED"
PARTIAL = "PARTIAL"
MISSING = "MISSING"
UNKNOWN = "UNKNOWN"


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff+#]+", "", (text or "").lower())


def _tokens(text: str) -> set[str]:
    value = (text or "").lower()
    en = re.findall(r"[a-z0-9+#.]{2,}", value)
    cn = re.findall(r"[\u4e00-\u9fff]{2,}", value)
    out = set(en)
    for run in cn:
        if len(run) <= 8:
            out.add(run)
        out.update(run[i:i+2] for i in range(max(0, len(run)-1)))
    return out


def _overlap(a: str, b: str) -> float:
    aa, bb = _tokens(a), _tokens(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / max(1, min(len(aa), len(bb)))


@dataclass(frozen=True)
class Requirement:
    requirement_id: str
    category: str
    text: str
    normalized_key: str
    importance: int = 3
    source_type: str = "derived"


class JobIntelligenceService:
    """Deterministic requirement decomposition and evidence-grounded match engine.

    The engine never infers that a participant owns a capability merely because the job requires it.
    Requirements and participant evidence are evaluated separately and every match result exposes the
    supporting evidence text or remains MISSING/UNKNOWN.
    """

    def __init__(self, job_store):
        self.job_store = job_store

    def derive_requirements(self, job: dict) -> list[Requirement]:
        reqs: list[Requirement] = []
        seen: set[str] = set()
        for skill in job.get("skills") or []:
            key = _norm(str(skill))
            if key and key not in seen:
                seen.add(key)
                reqs.append(Requirement(f"REQ-{uuid4().hex[:14].upper()}", "skill", str(skill).strip(), key, 4, "skills"))

        description = str(job.get("description") or "")
        lines = [x.strip(" -•\t") for x in re.split(r"[\n；;。]", description) if x.strip()]
        patterns = (
            ("credential", re.compile(r"(证书|认证|资格|license|certif)", re.I)),
            ("education", re.compile(r"(学历|本科|硕士|博士|degree|bachelor|master)", re.I)),
            ("experience", re.compile(r"(经验|年经验|经历|experience)", re.I)),
        )
        for line in lines[:80]:
            if len(line) > 220:
                continue
            category = "knowledge"
            if any(k in line for k in ("负责", "熟悉", "掌握", "具备", "要求", "能力", "经验")):
                category = "requirement"
            for name, pat in patterns:
                if pat.search(line):
                    category = name
                    break
            if category == "knowledge" and len(line) > 80:
                continue
            key = _norm(line)
            if not key or key in seen:
                continue
            seen.add(key)
            reqs.append(Requirement(f"REQ-{uuid4().hex[:14].upper()}", category, line, key[:160], 3, "description"))
            if len(reqs) >= 30:
                break
        return reqs

    def ensure_requirements(self, job_id: str, *, tenant_id: str) -> list[dict]:
        existing = self.job_store.list_requirements(job_id, tenant_id=tenant_id)
        if existing:
            return existing
        job = self.job_store.get(job_id, tenant_id=tenant_id)
        reqs = self.derive_requirements(job)
        self.job_store.replace_requirements(job_id, [r.__dict__ for r in reqs], tenant_id=tenant_id)
        return self.job_store.list_requirements(job_id, tenant_id=tenant_id)

    def match(self, *, job_id: str, tenant_id: str, profile, evidence_items: list[dict]) -> dict:
        job = self.job_store.get(job_id, tenant_id=tenant_id)
        requirements = self.ensure_requirements(job_id, tenant_id=tenant_id)
        participant = ParticipantProfile.from_legacy(profile)
        skills = [str(x) for x in participant.skills]
        evidence_texts = [participant.evidence_text] + participant.projects + participant.experience + [str(x.get("content") or "") for x in evidence_items]
        corpus = "\n".join(x for x in evidence_texts if x)
        skill_norms = {_norm(x): x for x in skills if _norm(x)}

        results = []
        counts = {MATCHED: 0, PARTIAL: 0, MISSING: 0, UNKNOWN: 0}
        for req in requirements:
            text = str(req.get("requirement_text") or req.get("text") or "")
            key = _norm(str(req.get("normalized_key") or text))
            category = str(req.get("category") or "requirement")
            direct_skill = next((raw for norm, raw in skill_norms.items() if key and (key in norm or norm in key)), "")
            best_evidence = ""
            best_score = 0.0
            for item in evidence_texts:
                score = _overlap(text, item)
                if score > best_score:
                    best_score, best_evidence = score, item

            if direct_skill:
                status, confidence = MATCHED, 0.94
                evidence = direct_skill
                reason = "participant profile contains a directly matching skill"
            elif best_score >= 0.62:
                status, confidence = MATCHED, min(0.92, 0.65 + best_score * 0.3)
                evidence = best_evidence[:500]
                reason = "participant evidence directly overlaps the requirement"
            elif best_score >= 0.30:
                status, confidence = PARTIAL, min(0.82, 0.4 + best_score * 0.5)
                evidence = best_evidence[:500]
                reason = "related evidence exists but does not fully establish the requirement"
            elif category in {"education", "credential"}:
                status, confidence = UNKNOWN, 0.58
                evidence = ""
                reason = "no explicit evidence was found for this formal requirement"
            else:
                status, confidence = MISSING, 0.78
                evidence = ""
                reason = "no supporting participant evidence was found"
            counts[status] += 1
            action = "maintain and document evidence" if status == MATCHED else (
                "collect stronger evidence or complete a targeted project" if status == PARTIAL else
                "verify this requirement and add explicit proof" if status == UNKNOWN else
                "build the capability through learning, project practice or supervised experience"
            )
            results.append({
                "requirement_id": req.get("requirement_id", ""),
                "requirement": text,
                "category": category,
                "importance": int(req.get("importance") or 3),
                "status": status,
                "evidence": evidence,
                "reason": reason,
                "confidence": round(confidence, 3),
                "recommended_action": action,
            })

        total = max(1, len(results))
        score = round((counts[MATCHED] + counts[PARTIAL] * 0.5) / total * 100, 1)
        return {
            "job": {k: job.get(k) for k in ("job_id", "title", "company", "city", "industry")},
            "summary": {**counts, "total": len(results), "match_score": score},
            "requirements": results,
            "policy": "job requirements and participant capabilities are evaluated independently; unsupported capabilities are never inferred from the job description",
        }
