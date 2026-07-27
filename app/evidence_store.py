from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path
from uuid import uuid4


COMMAND_PATTERNS = (
    r"^(帮我|请|继续|生成|修改|评分|评审|润色|重写|开始|确认|选择|上传|导出|查看|好的|好|可以|谢谢|ok|yes|no)",
    r"^(我选择|我要参加)(成长赛道|就业赛道)$",
)
FACT_MARKERS = (
    "我是", "我的", "我在", "我曾", "我参与", "我负责", "我获得", "我擅长", "我会", "我想从事", "目标岗位",
    "学校", "专业", "年级", "实习", "项目", "经历", "奖项", "证书", "技能", "负责", "参与", "完成", "访谈", "调研",
)

EVIDENCE_TRUST_STATES = {
    "SELF_REPORTED", "SOURCE_ATTACHED", "EXTRACTED", "AI_ASSESSED", "UNDER_REVIEW",
    "PARTIALLY_VERIFIED", "VERIFIED", "REJECTED", "CONTRADICTED",
}


def is_evidence_candidate(text: str) -> bool:
    """Conservative heuristic used before adding free-form chat to the student evidence ledger.

    Commands and conversational filler are excluded. Explicit profile/fact statements are accepted.
    False negatives are preferable to polluting the immutable student evidence ledger.
    """
    value = re.sub(r"\s+", " ", (text or "").strip())
    if len(value) < 4:
        return False
    if any(re.search(pattern, value, flags=re.I) for pattern in COMMAND_PATTERNS):
        # A command may still contain an explicit fact after a delimiter; require a strong marker plus enough detail.
        if not (len(value) >= 24 and sum(marker in value for marker in FACT_MARKERS) >= 2):
            return False
    if any(marker in value for marker in FACT_MARKERS):
        return True
    if re.search(r"\d+(?:\.\d+)?%?", value) and len(value) >= 12:
        return True
    return False


class EvidenceStore:
    """Tenant-scoped evidence ledger for student-provided facts only.

    Guidance, system prompts and ordinary chat commands must not be inserted here.
    """

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

    def add(
        self,
        session_id: str,
        source_type: str,
        source_label: str,
        content: str,
        verified: bool = False,
        *,
        tenant_id: str = "demo-org",
        owner_user_id: str = "",
    ) -> dict | None:
        text = content.strip()
        if len(text) < 2:
            return None
        evidence_id = f"EVID-{uuid4().hex[:10].upper()}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO evidence_items(evidence_id,session_id,tenant_id,owner_user_id,source_type,source_label,content,verified,metadata_json,version,updated_at,deleted_at,verification_status,verification_confidence)
                VALUES(?,?,?,?,?,?,?,?,?,1,CURRENT_TIMESTAMP,NULL,?,?)""",
                (evidence_id, session_id, tenant_id, owner_user_id, source_type, source_label[:160], text[:120000], int(verified), "{}", "VERIFIED" if verified else ("EXTRACTED" if source_type in {"file", "attachment", "parser"} else "SELF_REPORTED"), 1.0 if verified else 0.0),
            )
            conn.commit()
        return self.get(evidence_id, tenant_id=tenant_id)


    def add_structured(
        self,
        session_id: str,
        *,
        title: str,
        action: str,
        proof: str = "",
        capabilities: list[str] | None = None,
        verified: bool = False,
        tenant_id: str = "demo-org",
        owner_user_id: str = "",
        evidence_id: str | None = None,
    ) -> dict:
        evidence_id = evidence_id or f"EVID-{uuid4().hex[:10].upper()}"
        title = (title or "Evidence").strip()[:160]
        action = (action or "").strip()
        if len(action) < 2:
            raise ValueError("evidence action/content is required")
        metadata = {"action": action, "proof": proof or "", "capabilities": list(capabilities or [])}
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO evidence_items(evidence_id,session_id,tenant_id,owner_user_id,source_type,source_label,content,verified,metadata_json,version,updated_at,deleted_at,verification_status,verification_confidence)
                VALUES(?,?,?,?,?,?,?,?,?,1,CURRENT_TIMESTAMP,NULL,?,?)""",
                (evidence_id, session_id, tenant_id, owner_user_id, "structured", title, action[:120000], int(verified), json.dumps(metadata, ensure_ascii=False), "VERIFIED" if verified else "SELF_REPORTED", 1.0 if verified else 0.0),
            )
            conn.commit()
        return self.get(evidence_id, tenant_id=tenant_id)

    def update_structured(
        self,
        evidence_id: str,
        *,
        tenant_id: str,
        owner_user_id: str,
        title: str | None = None,
        action: str | None = None,
        proof: str | None = None,
        capabilities: list[str] | None = None,
        verified: bool | None = None,
        expected_version: int | None = None,
    ) -> dict:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM evidence_items WHERE evidence_id=? AND tenant_id=? AND owner_user_id=? AND deleted_at IS NULL",
                (evidence_id, tenant_id, owner_user_id),
            ).fetchone()
            if not row:
                raise KeyError(evidence_id)
            current = dict(row)
            actual = int(current.get("version") or 1)
            if expected_version is not None and expected_version != actual:
                from .unified_runtime_store import RuntimeVersionConflict
                raise RuntimeVersionConflict(evidence_id, expected_version, actual)
            try:
                metadata = json.loads(current.get("metadata_json") or "{}")
            except Exception:
                metadata = {}
            next_title = (title if title is not None else current.get("source_label") or "Evidence").strip()[:160]
            next_action = (action if action is not None else metadata.get("action") or current.get("content") or "").strip()
            if len(next_action) < 2:
                raise ValueError("evidence action/content is required")
            metadata["action"] = next_action
            if proof is not None:
                metadata["proof"] = proof
            if capabilities is not None:
                metadata["capabilities"] = list(capabilities)
            material_changed = (next_title != (current.get("source_label") or "")) or (next_action != (current.get("content") or ""))
            old_meta = json.loads(current.get("metadata_json") or "{}") if current.get("metadata_json") else {}
            material_changed = material_changed or (metadata.get("proof", "") != old_meta.get("proof", "")) or (list(metadata.get("capabilities") or []) != list(old_meta.get("capabilities") or []))
            current_status = str(current.get("verification_status") or ("VERIFIED" if current.get("verified") else "SELF_REPORTED"))
            next_status = current_status
            next_verified = int(current_status == "VERIFIED")
            invalidated = material_changed and current_status in {"VERIFIED", "PARTIALLY_VERIFIED", "REJECTED", "CONTRADICTED"}
            if invalidated:
                next_status = "EXTRACTED" if str(current.get("source_type") or "") in {"file", "attachment", "parser"} else "SELF_REPORTED"
                next_verified = 0
            conn.execute(
                """UPDATE evidence_items SET source_label=?,content=?,verified=?,metadata_json=?,verification_status=?,verification_confidence=?,verified_by=?,verified_at=?,version=version+1,updated_at=CURRENT_TIMESTAMP
                WHERE evidence_id=? AND tenant_id=? AND owner_user_id=?""",
                (next_title, next_action[:120000], next_verified, json.dumps(metadata, ensure_ascii=False), next_status, 0.0 if invalidated else float(current.get("verification_confidence") or 0), "" if invalidated else str(current.get("verified_by") or ""), None if invalidated else current.get("verified_at"), evidence_id, tenant_id, owner_user_id),
            )
            if invalidated:
                conn.execute(
                    """INSERT INTO evidence_item_verification_history
                    (history_id,tenant_id,session_id,evidence_id,previous_status,new_status,decision,confidence,method,reason,actor_user_id)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (f"EVH-{uuid4().hex[:18].upper()}", tenant_id, current.get("session_id") or "", evidence_id, current_status, next_status, "invalidated", 0.0, "material_edit", "Material edit invalidated previous verification", owner_user_id),
                )
            conn.commit()
        return self.get(evidence_id, tenant_id=tenant_id)

    def delete_item(
        self, evidence_id: str, *, tenant_id: str, owner_user_id: str, expected_version: int | None = None
    ) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT version FROM evidence_items WHERE evidence_id=? AND tenant_id=? AND owner_user_id=? AND deleted_at IS NULL",
                (evidence_id, tenant_id, owner_user_id),
            ).fetchone()
            if not row:
                return False
            actual = int(row["version"] or 1)
            if expected_version is not None and expected_version != actual:
                from .unified_runtime_store import RuntimeVersionConflict
                raise RuntimeVersionConflict(evidence_id, expected_version, actual)
            conn.execute(
                """UPDATE evidence_items SET deleted_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP,version=version+1
                WHERE evidence_id=? AND tenant_id=? AND owner_user_id=?""",
                (evidence_id, tenant_id, owner_user_id),
            )
            conn.commit()
        return True

    @staticmethod
    def to_workspace_item(row: dict) -> dict:
        try:
            meta = json.loads(row.get("metadata_json") or "{}")
        except Exception:
            meta = {}
        return {
            "id": row.get("evidence_id", ""),
            "title": row.get("source_label", "Evidence"),
            "action": meta.get("action") or row.get("content", ""),
            "proof": meta.get("proof", ""),
            "capabilities": list(meta.get("capabilities") or []),
            "verified": str(row.get("verification_status") or "") == "VERIFIED",
            "verificationStatus": str(row.get("verification_status") or ("VERIFIED" if row.get("verified") else "SELF_REPORTED")),
            "verificationConfidence": float(row.get("verification_confidence") or 0),
            "verifiedBy": str(row.get("verified_by") or ""),
            "verifiedAt": str(row.get("verified_at") or ""),
            "createdAt": str(row.get("created_at") or ""),
            "updatedAt": str(row.get("updated_at") or row.get("created_at") or ""),
            "_version": int(row.get("version") or 1),
        }

    def add_chat_candidate(
        self,
        session_id: str,
        content: str,
        *,
        tenant_id: str = "demo-org",
        owner_user_id: str = "",
        source_label: str = "用户对话",
    ) -> dict | None:
        if not is_evidence_candidate(content):
            return None
        return self.add(
            session_id,
            "student_chat",
            source_label,
            content,
            verified=False,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
        )

    def get(self, evidence_id: str, *, tenant_id: str | None = None) -> dict:
        sql = "SELECT * FROM evidence_items WHERE evidence_id=? AND deleted_at IS NULL"
        params: list[str] = [evidence_id]
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        with self._connect() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
        if not row:
            raise KeyError(evidence_id)
        return dict(row)

    def list_session(self, session_id: str, limit: int = 100, *, tenant_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM evidence_items WHERE session_id=? AND deleted_at IS NULL"
        params: list[object] = [session_id]
        if tenant_id is not None:
            sql += " AND tenant_id=?"
            params.append(tenant_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(r) for r in rows]

    def build_context(self, session_id: str, max_chars: int = 12000, *, tenant_id: str | None = None) -> str:
        items = self.list_session(session_id, limit=100, tenant_id=tenant_id)
        blocks: list[str] = []
        size = 0
        for item in reversed(items):
            block = f"[{item['evidence_id']}] 来源={item['source_label']}\n{item['content']}"
            if size + len(block) > max_chars:
                break
            blocks.append(block)
            size += len(block)
        return "\n\n".join(blocks)

    def link_text(self, session_id: str, text: str, max_links: int = 30, *, tenant_id: str | None = None) -> list[dict]:
        items = self.list_session(session_id, limit=100, tenant_id=tenant_id)
        if not items or not text.strip():
            return []
        sentences = [s.strip() for s in re.split(r"(?<=[。！？!?])|\n+", text) if len(s.strip()) >= 8]
        links: list[dict] = []
        for idx, sentence in enumerate(sentences):
            s_chars = set(re.sub(r"\s+", "", sentence))
            if len(s_chars) < 5:
                continue
            best = None
            best_score = 0.0
            for item in items:
                e_chars = set(re.sub(r"\s+", "", item["content"]))
                if not e_chars:
                    continue
                overlap = len(s_chars & e_chars) / max(1, min(len(s_chars), len(e_chars)))
                nums = set(re.findall(r"\d+(?:\.\d+)?%?", sentence))
                e_nums = set(re.findall(r"\d+(?:\.\d+)?%?", item["content"]))
                if nums and nums <= e_nums:
                    overlap += 0.18
                if overlap > best_score:
                    best_score = overlap
                    best = item
            if best and best_score >= 0.34:
                links.append({
                    "sentence_index": idx,
                    "sentence": sentence[:320],
                    "evidence_id": best["evidence_id"],
                    "source_label": best["source_label"],
                    "confidence": round(min(best_score, 0.99), 3),
                })
            if len(links) >= max_links:
                break
        return links


    def verify_item(
        self, evidence_id: str, *, tenant_id: str, owner_user_id: str, decision: str,
        actor_user_id: str, reason: str = "", confidence: float = 1.0, method: str = "human_review"
    ) -> dict:
        mapping = {
            "submit_review": "UNDER_REVIEW", "verified": "VERIFIED", "partial": "PARTIALLY_VERIFIED",
            "rejected": "REJECTED", "contradicted": "CONTRADICTED",
        }
        if decision not in mapping:
            raise ValueError("invalid evidence verification decision")
        new_status = mapping[decision]
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM evidence_items WHERE evidence_id=? AND tenant_id=? AND owner_user_id=? AND deleted_at IS NULL",
                (evidence_id, tenant_id, owner_user_id),
            ).fetchone()
            if not row:
                raise KeyError(evidence_id)
            current = dict(row)
            previous = str(current.get("verification_status") or ("VERIFIED" if current.get("verified") else "SELF_REPORTED"))
            verified = int(new_status == "VERIFIED")
            conn.execute(
                """UPDATE evidence_items SET verification_status=?,verification_method=?,verification_confidence=?,verified=?,verified_by=?,verified_at=CURRENT_TIMESTAMP,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE evidence_id=?""",
                (new_status, method, max(0.0, min(float(confidence), 1.0)), verified, actor_user_id, evidence_id),
            )
            conn.execute(
                """INSERT INTO evidence_item_verification_history
                (history_id,tenant_id,session_id,evidence_id,previous_status,new_status,decision,confidence,method,reason,actor_user_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (f"EVH-{uuid4().hex[:18].upper()}", tenant_id, current.get("session_id") or "", evidence_id, previous, new_status, decision, max(0.0, min(float(confidence), 1.0)), method, reason[:12000], actor_user_id),
            )
            conn.commit()
        return self.get(evidence_id, tenant_id=tenant_id)

    def verification_history(self, evidence_id: str, *, tenant_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM evidence_item_verification_history WHERE tenant_id=? AND evidence_id=? ORDER BY created_at DESC",
                (tenant_id, evidence_id),
            ).fetchall()
        return [dict(x) for x in rows]

    def delete_session(self, session_id: str, *, tenant_id: str) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM evidence_items WHERE session_id=? AND tenant_id=?", (session_id, tenant_id))
            conn.commit()
            return int(cur.rowcount)
