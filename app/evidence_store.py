from __future__ import annotations

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
                """INSERT INTO evidence_items(evidence_id,session_id,tenant_id,owner_user_id,source_type,source_label,content,verified)
                VALUES(?,?,?,?,?,?,?,?)""",
                (evidence_id, session_id, tenant_id, owner_user_id, source_type, source_label[:160], text[:120000], int(verified)),
            )
            conn.commit()
        return self.get(evidence_id, tenant_id=tenant_id)

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
        sql = "SELECT * FROM evidence_items WHERE evidence_id=?"
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
        sql = "SELECT * FROM evidence_items WHERE session_id=?"
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

    def delete_session(self, session_id: str, *, tenant_id: str) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM evidence_items WHERE session_id=? AND tenant_id=?", (session_id, tenant_id))
            conn.commit()
            return int(cur.rowcount)
