from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .embedding_gateway import EmbeddingGateway

STATUS_SUPPORTED = "SUPPORTED"
STATUS_PARTIAL = "PARTIALLY_SUPPORTED"
STATUS_CONTRADICTED = "CONTRADICTED"
STATUS_UNSUPPORTED = "UNSUPPORTED"
STATUS_UNVERIFIED = "UNVERIFIED"

_NEGATION = re.compile(r"(?:没有|未曾|未|无|不|never|not|no\b)", re.I)
_NUMBER = re.compile(r"\d+(?:\.\d+)?%?")
_HIGH_RISK = re.compile(r"(?:奖项|获奖|证书|认证|学历|学位|收入|薪资|人数|比例|百分比|排名|金额|营收|利润|certificate|award|degree|salary|income|revenue|rank)", re.I)


def _tokens(text: str) -> set[str]:
    value = re.sub(r"\s+", "", (text or "").lower())
    english = re.findall(r"[a-z0-9_+-]{2,}", value)
    cn_runs = re.findall(r"[\u4e00-\u9fff]+", value)
    grams: list[str] = []
    for run in cn_runs:
        grams.extend(run[i:i + 2] for i in range(max(0, len(run) - 1)))
        if len(run) <= 8:
            grams.append(run)
    return set(english + grams + _NUMBER.findall(value))


def _lexical_score(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, min(len(ta), len(tb)))


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return max(-1.0, min(1.0, dot / (na * nb)))


@dataclass
class VerificationResult:
    status: str
    confidence: float
    best_evidence_id: str = ""
    reason: str = ""
    candidates: list[dict] | None = None
    risk_level: str = "normal"
    requires_human_review: bool = False


class EvidenceVerificationService:
    """Claim/evidence verifier with conservative semantics.

    It combines exact/lexical checks, number consistency, negation contradiction and optional semantic
    embeddings. local-hash vectors are never treated as semantic proof. In ambiguous cases the result
    stays UNVERIFIED rather than manufacturing certainty.
    """

    def __init__(self, embedding_gateway: EmbeddingGateway):
        self.embedding_gateway = embedding_gateway

    def verify(self, claim: str, evidence_items: list[dict]) -> VerificationResult:
        claim = (claim or "").strip()
        if not claim:
            return VerificationResult(STATUS_UNVERIFIED, 0.0, reason="empty claim")
        risk_level = "high" if (_NUMBER.search(claim) or _HIGH_RISK.search(claim)) else "normal"
        if not evidence_items:
            return VerificationResult(STATUS_UNSUPPORTED, 0.98, reason="no evidence available", risk_level=risk_level, requires_human_review=(risk_level == "high"))

        texts = [claim] + [str(x.get("content") or "") for x in evidence_items]
        emb = self.embedding_gateway.embed(texts)
        claim_vec = emb.vectors[0] if emb.vectors else []
        semantic_is_real = emb.provider != "local_hash" and self.embedding_gateway.semantic_enabled
        claim_nums = set(_NUMBER.findall(claim))
        claim_neg = bool(_NEGATION.search(claim))

        ranked: list[dict] = []
        for idx, item in enumerate(evidence_items):
            text = str(item.get("content") or "")
            lexical = _lexical_score(claim, text)
            semantic = _cosine(claim_vec, emb.vectors[idx + 1]) if len(emb.vectors) > idx + 1 else 0.0
            evidence_nums = set(_NUMBER.findall(text))
            number_match = 1.0 if not claim_nums else (len(claim_nums & evidence_nums) / max(1, len(claim_nums)))
            number_conflict = bool(claim_nums and evidence_nums and not (claim_nums & evidence_nums) and lexical >= 0.22)
            negation_conflict = claim_neg != bool(_NEGATION.search(text)) and lexical >= 0.45
            semantic_component = max(0.0, semantic) if semantic_is_real else 0.0
            score = lexical * 0.72 + semantic_component * 0.28
            if claim_nums:
                score = score * 0.82 + number_match * 0.18
            ranked.append({
                "evidence_id": item.get("evidence_id", ""),
                "source_label": item.get("source_label", ""),
                "lexical": round(lexical, 4),
                "semantic": round(max(0.0, semantic), 4),
                "number_match": round(number_match, 4),
                "number_conflict": number_conflict,
                "negation_conflict": negation_conflict,
                "score": round(score, 4),
            })
        ranked.sort(key=lambda x: x["score"], reverse=True)
        best = ranked[0]

        if any(x["number_conflict"] or x["negation_conflict"] for x in ranked[:3]):
            conflict = next(x for x in ranked[:3] if x["number_conflict"] or x["negation_conflict"])
            return VerificationResult(
                STATUS_CONTRADICTED,
                min(0.99, max(0.65, conflict["lexical"])),
                conflict["evidence_id"],
                "evidence contains a conflicting number or negation for a closely related claim",
                ranked[:5],
                risk_level=risk_level, requires_human_review=True,
            )

        if claim_nums and best["number_match"] < 1.0:
            if best["score"] >= 0.42:
                return VerificationResult(STATUS_PARTIAL, min(0.89, best["score"]), best["evidence_id"], "related evidence found but numeric facts are not fully supported", ranked[:5], risk_level=risk_level, requires_human_review=True)
            return VerificationResult(STATUS_UNSUPPORTED, 0.9, best["evidence_id"], "claim contains numeric facts that are not present in evidence", ranked[:5], risk_level=risk_level, requires_human_review=True)

        if risk_level == "high" and not (best["lexical"] >= 0.78 and best["number_match"] >= 1.0):
            return VerificationResult(STATUS_PARTIAL if best["score"] >= 0.42 else STATUS_UNVERIFIED, min(0.84, max(best["score"], best["lexical"])), best["evidence_id"], "high-risk factual claim requires explicit evidence and human review before final acceptance", ranked[:5], risk_level=risk_level, requires_human_review=True)

        if best["score"] >= 0.72 or (best["lexical"] >= 0.78 and best["number_match"] >= 1.0):
            return VerificationResult(STATUS_SUPPORTED, min(0.99, max(best["score"], best["lexical"])), best["evidence_id"], "claim is directly supported by the best matching evidence", ranked[:5], risk_level=risk_level, requires_human_review=(risk_level == "high"))
        if best["score"] >= 0.42 or best["lexical"] >= 0.42:
            return VerificationResult(STATUS_PARTIAL, min(0.88, max(best["score"], best["lexical"])), best["evidence_id"], "evidence is related but does not fully establish the claim", ranked[:5], risk_level=risk_level, requires_human_review=(risk_level == "high"))
        if semantic_is_real and best["semantic"] < 0.2 and best["lexical"] < 0.18:
            return VerificationResult(STATUS_UNSUPPORTED, 0.75, best["evidence_id"], "no sufficiently related evidence was retrieved", ranked[:5], risk_level=risk_level, requires_human_review=(risk_level == "high"))
        return VerificationResult(STATUS_UNVERIFIED, min(0.5, max(best["score"], best["lexical"])), best["evidence_id"], "insufficient evidence for a reliable support decision", ranked[:5], risk_level=risk_level, requires_human_review=(risk_level == "high"))
