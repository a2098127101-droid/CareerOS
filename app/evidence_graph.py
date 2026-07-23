from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4


_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])|\n+")


def _fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", "", text).lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _tokens(text: str) -> set[str]:
    value = re.sub(r"\s+", "", text.lower())
    english = re.findall(r"[a-z0-9_+-]{2,}", value)
    chinese = re.findall(r"[\u4e00-\u9fff]+", value)
    grams: list[str] = []
    for run in chinese:
        grams.extend(run[i:i+2] for i in range(max(0, len(run)-1)))
        if len(run) <= 8:
            grams.append(run)
    nums = re.findall(r"\d+(?:\.\d+)?%?", value)
    return set(english + grams + nums)


def _support_score(claim: str, evidence: str) -> float:
    a, b = _tokens(claim), _tokens(evidence)
    if not a or not b:
        return 0.0
    overlap = len(a & b) / max(1, min(len(a), len(b)))
    claim_nums = set(re.findall(r"\d+(?:\.\d+)?%?", claim))
    evidence_nums = set(re.findall(r"\d+(?:\.\d+)?%?", evidence))
    if claim_nums:
        if claim_nums <= evidence_nums:
            overlap += 0.2
        elif claim_nums - evidence_nums:
            overlap -= 0.25
    return max(0.0, min(0.99, overlap))


class EvidenceGraphStore:
    """Claim-level provenance graph for evidence, artifacts, reviews and teacher feedback."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Ensure the canonical SQLite compatibility schema via the centralized migration layer.

        Store modules no longer own CREATE TABLE/CREATE INDEX DDL. The checked-in schema manifest
        and versioned migrations are the single compatibility source used by both local SQLite and
        Alembic/PostgreSQL provisioning.
        """
        from .migrations import run_migrations
        run_migrations(str(self.db_path))

    def _edge(
        self,
        conn: sqlite3.Connection,
        *,
        tenant_id: str,
        session_id: str,
        from_type: str,
        from_id: str,
        relation: str,
        to_type: str,
        to_id: str,
        confidence: float = 1.0,
        metadata: dict | None = None,
    ) -> str:
        existing = conn.execute(
            """SELECT edge_id FROM evidence_graph_edges WHERE tenant_id=? AND from_type=? AND from_id=? AND relation=? AND to_type=? AND to_id=?""",
            (tenant_id, from_type, from_id, relation, to_type, to_id),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE evidence_graph_edges SET confidence=?,metadata_json=? WHERE edge_id=?",
                (float(confidence), json.dumps(metadata or {}, ensure_ascii=False), existing["edge_id"]),
            )
            return existing["edge_id"]
        edge_id = f"EDGE-{uuid4().hex[:12].upper()}"
        conn.execute(
            """INSERT INTO evidence_graph_edges(edge_id,tenant_id,session_id,from_type,from_id,relation,to_type,to_id,confidence,metadata_json)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                edge_id, tenant_id, session_id, from_type, from_id, relation, to_type, to_id,
                float(confidence), json.dumps(metadata or {}, ensure_ascii=False),
            ),
        )
        return edge_id

    def _claim(
        self,
        conn: sqlite3.Connection,
        *,
        tenant_id: str,
        session_id: str,
        text: str,
        claim_type: str,
        status: str = "unverified",
    ) -> str:
        fp = _fingerprint(text)
        row = conn.execute(
            "SELECT claim_id FROM evidence_claims WHERE tenant_id=? AND session_id=? AND fingerprint=? AND claim_type=?",
            (tenant_id, session_id, fp, claim_type),
        ).fetchone()
        if row:
            return row["claim_id"]
        claim_id = f"CLM-{uuid4().hex[:12].upper()}"
        conn.execute(
            """INSERT INTO evidence_claims(claim_id,tenant_id,session_id,claim_text,claim_type,status,fingerprint)
            VALUES(?,?,?,?,?,?,?)""",
            (claim_id, tenant_id, session_id, text[:4000], claim_type, status, fp),
        )
        return claim_id

    def trace_artifact_version(
        self,
        *,
        tenant_id: str,
        session_id: str,
        artifact_id: str,
        version_id: str,
        content: str,
        evidence_items: list[dict],
    ) -> dict:
        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(content or "") if len(s.strip()) >= 8]
        linked = 0
        unsupported = 0
        claim_ids: list[str] = []
        with self._lock, self._connect() as conn:
            self._edge(
                conn, tenant_id=tenant_id, session_id=session_id,
                from_type="artifact", from_id=artifact_id, relation="has_version",
                to_type="artifact_version", to_id=version_id,
            )
            for idx, sentence in enumerate(sentences[:300]):
                claim_id = self._claim(
                    conn, tenant_id=tenant_id, session_id=session_id, text=sentence,
                    claim_type="artifact_claim", status="unverified",
                )
                claim_ids.append(claim_id)
                self._edge(
                    conn, tenant_id=tenant_id, session_id=session_id,
                    from_type="artifact_version", from_id=version_id, relation="contains_claim",
                    to_type="claim", to_id=claim_id, metadata={"sentence_index": idx},
                )
                ranked: list[tuple[float, dict]] = []
                for item in evidence_items:
                    score = _support_score(sentence, item.get("content", ""))
                    if score >= 0.34:
                        ranked.append((score, item))
                ranked.sort(key=lambda x: x[0], reverse=True)
                for score, item in ranked[:3]:
                    self._edge(
                        conn, tenant_id=tenant_id, session_id=session_id,
                        from_type="claim", from_id=claim_id, relation="supported_by",
                        to_type="evidence", to_id=item["evidence_id"], confidence=score,
                        metadata={"source_label": item.get("source_label", "")},
                    )
                    linked += 1
                if not ranked:
                    unsupported += 1
            conn.commit()
        return {
            "artifact_id": artifact_id,
            "version_id": version_id,
            "claims": len(claim_ids),
            "evidence_links": linked,
            "unsupported_claims": unsupported,
        }

    def record_review(
        self,
        *,
        tenant_id: str,
        session_id: str,
        artifact_id: str,
        version_id: str,
        report: dict,
        created_by: str = "",
    ) -> dict:
        review_id = f"REV-{uuid4().hex[:12].upper()}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO review_records(review_id,tenant_id,session_id,artifact_id,version_id,total_score,report_json,created_by)
                VALUES(?,?,?,?,?,?,?,?)""",
                (
                    review_id, tenant_id, session_id, artifact_id, version_id,
                    int(report.get("total_score") or 0), json.dumps(report, ensure_ascii=False), created_by,
                ),
            )
            if version_id:
                self._edge(
                    conn, tenant_id=tenant_id, session_id=session_id,
                    from_type="review", from_id=review_id, relation="evaluates",
                    to_type="artifact_version", to_id=version_id,
                )
            findings = []
            for key, ctype in [
                ("fatal_issues", "review_finding"),
                ("structural_issues", "review_finding"),
                ("revision_priority", "review_recommendation"),
            ]:
                for item in report.get(key, []) or []:
                    if not str(item).strip():
                        continue
                    claim_id = self._claim(
                        conn, tenant_id=tenant_id, session_id=session_id,
                        text=str(item), claim_type=ctype, status="reviewer_generated",
                    )
                    findings.append(claim_id)
                    self._edge(
                        conn, tenant_id=tenant_id, session_id=session_id,
                        from_type="review", from_id=review_id, relation="produces_finding",
                        to_type="claim", to_id=claim_id,
                    )
            conn.commit()
        return {"review_id": review_id, "artifact_id": artifact_id, "version_id": version_id, "findings": findings}

    def record_feedback(
        self,
        *,
        tenant_id: str,
        session_id: str,
        feedback_id: str,
        content: str,
        artifact_id: str = "",
        version_id: str = "",
    ) -> dict:
        with self._lock, self._connect() as conn:
            claim_id = self._claim(
                conn, tenant_id=tenant_id, session_id=session_id,
                text=content, claim_type="teacher_guidance", status="human_guidance",
            )
            self._edge(
                conn, tenant_id=tenant_id, session_id=session_id,
                from_type="feedback", from_id=feedback_id, relation="expresses",
                to_type="claim", to_id=claim_id,
            )
            if version_id:
                self._edge(
                    conn, tenant_id=tenant_id, session_id=session_id,
                    from_type="feedback", from_id=feedback_id, relation="targets",
                    to_type="artifact_version", to_id=version_id,
                )
            elif artifact_id:
                self._edge(
                    conn, tenant_id=tenant_id, session_id=session_id,
                    from_type="feedback", from_id=feedback_id, relation="targets",
                    to_type="artifact", to_id=artifact_id,
                )
            conn.commit()
        return {"feedback_id": feedback_id, "claim_id": claim_id}

    def link_revision(
        self,
        *,
        tenant_id: str,
        session_id: str,
        previous_version_id: str,
        new_version_id: str,
        review_id: str = "",
        feedback_ids: list[str] | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            if previous_version_id and new_version_id:
                self._edge(
                    conn, tenant_id=tenant_id, session_id=session_id,
                    from_type="artifact_version", from_id=new_version_id, relation="revises",
                    to_type="artifact_version", to_id=previous_version_id,
                )
            if review_id and new_version_id:
                self._edge(
                    conn, tenant_id=tenant_id, session_id=session_id,
                    from_type="artifact_version", from_id=new_version_id, relation="responds_to",
                    to_type="review", to_id=review_id,
                )
            for fid in feedback_ids or []:
                self._edge(
                    conn, tenant_id=tenant_id, session_id=session_id,
                    from_type="artifact_version", from_id=new_version_id, relation="responds_to",
                    to_type="feedback", to_id=fid,
                )
            conn.commit()

    def latest_review(self, session_id: str, *, tenant_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_records WHERE session_id=? AND tenant_id=? ORDER BY created_at DESC LIMIT 1",
                (session_id, tenant_id),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["report"] = json.loads(d.pop("report_json") or "{}")
        return d

    def session_graph(self, session_id: str, *, tenant_id: str) -> dict:
        with self._connect() as conn:
            claims = [dict(r) for r in conn.execute(
                "SELECT * FROM evidence_claims WHERE session_id=? AND tenant_id=? ORDER BY created_at",
                (session_id, tenant_id),
            ).fetchall()]
            edges = [dict(r) for r in conn.execute(
                "SELECT * FROM evidence_graph_edges WHERE session_id=? AND tenant_id=? ORDER BY created_at",
                (session_id, tenant_id),
            ).fetchall()]
            reviews = [dict(r) for r in conn.execute(
                "SELECT * FROM review_records WHERE session_id=? AND tenant_id=? ORDER BY created_at",
                (session_id, tenant_id),
            ).fetchall()]
        for edge in edges:
            try:
                edge["metadata"] = json.loads(edge.pop("metadata_json") or "{}")
            except Exception:
                edge["metadata"] = {}
        for review in reviews:
            try:
                review["report"] = json.loads(review.pop("report_json") or "{}")
            except Exception:
                review["report"] = {}
        with self._connect() as conn:
            histories = [dict(r) for r in conn.execute(
                "SELECT * FROM evidence_verification_history WHERE session_id=? AND tenant_id=? ORDER BY created_at",
                (session_id, tenant_id),
            ).fetchall()]
        return {"claims": claims, "edges": edges, "reviews": reviews, "verification_history": histories}

    def list_claims(self, session_id: str, *, tenant_id: str, claim_ids: list[str] | None = None) -> list[dict]:
        sql = "SELECT * FROM evidence_claims WHERE session_id=? AND tenant_id=?"
        params: list[object] = [session_id, tenant_id]
        if claim_ids:
            placeholders = ",".join("?" for _ in claim_ids)
            sql += f" AND claim_id IN ({placeholders})"
            params.extend(claim_ids)
        sql += " ORDER BY created_at"
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]

    def update_claim_verification(
        self, claim_id: str, *, tenant_id: str, status: str, confidence: float, verified_by: str = "system",
        verifier_type: str = "ai", reason: str = "", session_id: str = "", risk_level: str = "normal",
        requires_human_review: bool = False,
    ) -> dict:
        allowed = {"SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "UNVERIFIED"}
        if status not in allowed:
            raise ValueError("invalid verification status")
        with self._lock, self._connect() as conn:
            before = conn.execute("SELECT * FROM evidence_claims WHERE claim_id=? AND tenant_id=?", (claim_id, tenant_id)).fetchone()
            if not before:
                raise KeyError(claim_id)
            resolved_session = session_id or before["session_id"]
            previous = before["verification_status"] if "verification_status" in before.keys() else "UNVERIFIED"
            conn.execute(
                """UPDATE evidence_claims SET verification_status=?,verification_confidence=?,verified_by=?,verified_at=CURRENT_TIMESTAMP,
                risk_level=?,requires_human_review=?,updated_at=CURRENT_TIMESTAMP WHERE claim_id=? AND tenant_id=?""",
                (status, float(confidence), verified_by, risk_level, 1 if requires_human_review else 0, claim_id, tenant_id),
            )
            conn.execute(
                """INSERT INTO evidence_verification_history(verification_id,tenant_id,session_id,claim_id,previous_status,new_status,confidence,verifier_type,verified_by,reason,risk_level,requires_human_review)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (f"VFY-{uuid4().hex[:14].upper()}", tenant_id, resolved_session, claim_id, previous or "UNVERIFIED", status, float(confidence), verifier_type, verified_by, reason[:4000], risk_level, 1 if requires_human_review else 0),
            )
            row = conn.execute("SELECT * FROM evidence_claims WHERE claim_id=? AND tenant_id=?", (claim_id, tenant_id)).fetchone()
            conn.commit()
        return dict(row)

    def verification_history(self, claim_id: str, *, tenant_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_verification_history WHERE claim_id=? AND tenant_id=? ORDER BY created_at",
                (claim_id, tenant_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def artifact_trace(self, artifact_id: str, *, tenant_id: str) -> dict:
        with self._connect() as conn:
            versions = [dict(r) for r in conn.execute(
                "SELECT * FROM artifact_versions WHERE artifact_id=? AND tenant_id=? ORDER BY version",
                (artifact_id, tenant_id),
            ).fetchall()]
            version_ids = [v["version_id"] for v in versions]
            if not version_ids:
                return {"artifact_id": artifact_id, "versions": [], "claims": [], "edges": [], "evidence": [], "reviews": []}
            placeholders = ",".join("?" for _ in version_ids)
            edges = [dict(r) for r in conn.execute(
                f"""SELECT * FROM evidence_graph_edges WHERE tenant_id=? AND (
                (from_type='artifact' AND from_id=?) OR
                (from_type='artifact_version' AND from_id IN ({placeholders})) OR
                (to_type='artifact_version' AND to_id IN ({placeholders}))
                ) ORDER BY created_at""",
                tuple([tenant_id, artifact_id] + version_ids + version_ids),
            ).fetchall()]
            claim_ids = {e["to_id"] for e in edges if e["to_type"] == "claim"} | {e["from_id"] for e in edges if e["from_type"] == "claim"}
            claims = []
            evidence = []
            if claim_ids:
                q = ",".join("?" for _ in claim_ids)
                claims = [dict(r) for r in conn.execute(f"SELECT * FROM evidence_claims WHERE claim_id IN ({q})", tuple(claim_ids)).fetchall()]
                claim_edges = [dict(r) for r in conn.execute(
                    f"SELECT * FROM evidence_graph_edges WHERE tenant_id=? AND (from_id IN ({q}) OR to_id IN ({q})) ORDER BY created_at",
                    tuple([tenant_id] + list(claim_ids) + list(claim_ids)),
                ).fetchall()]
                known = {e["edge_id"] for e in edges}
                edges.extend(e for e in claim_edges if e["edge_id"] not in known)
            evidence_ids = {e["to_id"] for e in edges if e["to_type"] == "evidence"} | {e["from_id"] for e in edges if e["from_type"] == "evidence"}
            if evidence_ids:
                q = ",".join("?" for _ in evidence_ids)
                evidence = [dict(r) for r in conn.execute(f"SELECT * FROM evidence_items WHERE evidence_id IN ({q})", tuple(evidence_ids)).fetchall()]
            reviews = [dict(r) for r in conn.execute(
                "SELECT * FROM review_records WHERE artifact_id=? AND tenant_id=? ORDER BY created_at", (artifact_id, tenant_id)
            ).fetchall()]
        return {"artifact_id": artifact_id, "versions": versions, "claims": claims, "edges": edges, "evidence": evidence, "reviews": reviews}

    def delete_session(self, session_id: str, *, tenant_id: str) -> dict:
        with self._lock, self._connect() as conn:
            edges = conn.execute("DELETE FROM evidence_graph_edges WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)).rowcount
            reviews = conn.execute("DELETE FROM review_records WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)).rowcount
            history = conn.execute("DELETE FROM evidence_verification_history WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)).rowcount
            claims = conn.execute("DELETE FROM evidence_claims WHERE session_id=? AND tenant_id=?", (session_id, tenant_id)).rowcount
            conn.commit()
            return {"claims": int(claims), "reviews": int(reviews), "edges": int(edges), "verification_history": int(history)}
