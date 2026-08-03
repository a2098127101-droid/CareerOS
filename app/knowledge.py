from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .models import KnowledgeRef
from .embedding_gateway import EmbeddingGateway, EmbeddingConfig, local_hash_embedding
from .retrieval import RerankerGateway, bm25_scores


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _hash_embedding(text: str, dims: int = 256) -> list[float]:
    return local_hash_embedding(text, dims)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return max(-1.0, min(1.0, sum(x*y for x, y in zip(a, b))))


@dataclass
class SearchHit:
    source_id: str
    source_title: str
    chunk_id: str
    content: str
    score: float
    chunk_index: int


class KnowledgeStore:
    def __init__(
        self,
        db_path: str,
        embedding_gateway: EmbeddingGateway | None = None,
        reranker_gateway: RerankerGateway | None = None,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.embedding_gateway = embedding_gateway or EmbeddingGateway(EmbeddingConfig())
        self.reranker_gateway = reranker_gateway or RerankerGateway()
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

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1800, overlap: int = 180) -> list[str]:
        clean = re.sub(r"\r\n?", "\n", text).strip()
        if not clean:
            return []
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", clean) if p.strip()]
        if len(paragraphs) <= 1:
            paragraphs = [p.strip() for p in clean.split("\n") if p.strip()]
        chunks: list[str] = []
        buf = ""
        for p in paragraphs:
            candidate = (buf + "\n" + p).strip() if buf else p
            if len(candidate) <= chunk_size:
                buf = candidate
                continue
            if buf:
                chunks.append(buf)
                tail = buf[-overlap:] if overlap else ""
                buf = (tail + "\n" + p).strip()
            else:
                start = 0
                while start < len(p):
                    end = min(len(p), start + chunk_size)
                    chunks.append(p[start:end])
                    start = max(end - overlap, start + 1)
                buf = ""
        if buf:
            chunks.append(buf)
        return [c for c in chunks if c.strip()]

    def ingest(self, *, title: str, filename: str, mime_type: str, text: str, scope: str = "global", tags: list[str] | None = None, category: str = "other", authority: str = "internal", effective_year: str = "", priority: int = 50, tenant_id: str = "global") -> dict:
        chunks = self.chunk_text(text)
        source_id = str(uuid4())
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO knowledge_sources(source_id,tenant_id,title,filename,mime_type,scope,tags,active,char_count,chunk_count,category,authority,effective_year,priority)
                VALUES(?,?,?,?,?,?,?,1,?,?,?,?,?,?)""",
                (source_id, tenant_id, title, filename, mime_type, scope, json.dumps(tags or [], ensure_ascii=False), len(text), len(chunks), category, authority, effective_year, int(priority)),
            )
            for idx, chunk in enumerate(chunks):
                chunk_id = str(uuid4())
                digest = _content_hash(chunk)
                emb = self.embedding_gateway.embed([chunk])
                model_name = emb.model
                vector = emb.vectors[0] if emb.vectors else _hash_embedding(chunk)
                conn.execute(
                    "INSERT INTO knowledge_chunks(chunk_id,source_id,chunk_index,content,content_hash,embedding_model) VALUES(?,?,?,?,?,?)",
                    (chunk_id, source_id, idx, chunk, digest, model_name),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO knowledge_embeddings(chunk_id,source_id,embedding_model,embedding_version,vector_json,content_hash,provider,dimensions,warning) VALUES(?,?,?,?,?,?,?,?,?)",
                    (chunk_id, source_id, model_name, "1", json.dumps(vector), digest, emb.provider, emb.dimensions or len(vector), emb.warning),
                )
                try:
                    conn.execute("INSERT INTO knowledge_chunks_fts(chunk_id,source_id,content) VALUES(?,?,?)", (chunk_id, source_id, chunk))
                except sqlite3.DatabaseError:
                    pass
            conn.commit()
        return {"source_id": source_id, "tenant_id": tenant_id, "title": title, "chunk_count": len(chunks), "char_count": len(text), "scope": scope, "category": category, "authority": authority, "effective_year": effective_year, "priority": priority}

    def list_sources(self, tenant_id: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if tenant_id is None:
                rows = conn.execute("SELECT * FROM knowledge_sources ORDER BY updated_at DESC").fetchall()
            else:
                rows = conn.execute("SELECT * FROM knowledge_sources WHERE tenant_id IN (?,'global') ORDER BY updated_at DESC", (tenant_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["tags"] = json.loads(d.get("tags") or "[]")
            d["active"] = bool(d["active"])
            result.append(d)
        return result

    def update_source(self, source_id: str, *, title: str | None = None, scope: str | None = None, tags: list[str] | None = None, active: bool | None = None, category: str | None = None, authority: str | None = None, effective_year: str | None = None, priority: int | None = None, tenant_id: str | None = None) -> None:
        fields: list[str] = []
        values: list[object] = []
        if title is not None:
            fields.append("title=?"); values.append(title)
        if scope is not None:
            fields.append("scope=?"); values.append(scope)
        if tags is not None:
            fields.append("tags=?"); values.append(json.dumps(tags, ensure_ascii=False))
        if active is not None:
            fields.append("active=?"); values.append(1 if active else 0)
        if category is not None:
            fields.append("category=?"); values.append(category)
        if authority is not None:
            fields.append("authority=?"); values.append(authority)
        if effective_year is not None:
            fields.append("effective_year=?"); values.append(effective_year)
        if priority is not None:
            fields.append("priority=?"); values.append(int(priority))
        if not fields:
            return
        fields.append("updated_at=CURRENT_TIMESTAMP")
        values.append(source_id)
        with self._lock, self._connect() as conn:
            sql = f"UPDATE knowledge_sources SET {','.join(fields)} WHERE source_id=?"
            if tenant_id is not None:
                sql += " AND tenant_id=?"; values.append(tenant_id)
            conn.execute(sql, values)
            conn.commit()

    def delete_source(self, source_id: str, *, tenant_id: str | None = None) -> None:
        with self._lock, self._connect() as conn:
            if tenant_id is not None:
                owner = conn.execute("SELECT 1 FROM knowledge_sources WHERE source_id=? AND tenant_id=?", (source_id,tenant_id)).fetchone()
                if not owner: raise KeyError(source_id)
            try:
                conn.execute("DELETE FROM knowledge_chunks_fts WHERE source_id=?", (source_id,))
            except sqlite3.DatabaseError:
                pass
            conn.execute("DELETE FROM knowledge_embeddings WHERE source_id=?", (source_id,))
            conn.execute("DELETE FROM knowledge_chunks WHERE source_id=?", (source_id,))
            conn.execute("DELETE FROM knowledge_sources WHERE source_id=?", (source_id,))
            conn.commit()

    @staticmethod
    def _terms(query: str) -> list[str]:
        q = query.lower()
        english = re.findall(r"[a-z0-9_+-]{2,}", q)
        chinese_runs = re.findall(r"[\u4e00-\u9fff]{2,}", q)
        terms = english[:20]
        for run in chinese_runs[:12]:
            if len(run) <= 6:
                terms.append(run)
            terms.extend(run[i:i+2] for i in range(max(0, len(run)-1)))
        return list(dict.fromkeys(t for t in terms if t.strip()))[:60]

    def rebuild_hybrid_index(self, *, only_missing: bool = False, tenant_id: str | None = None) -> dict:
        indexed = 0
        with self._lock, self._connect() as conn:
            if tenant_id:
                rows = conn.execute("""SELECT c.chunk_id,c.source_id,c.content,COALESCE(c.content_hash,'') content_hash
                    FROM knowledge_chunks c JOIN knowledge_sources s ON s.source_id=c.source_id WHERE s.tenant_id=?""", (tenant_id,)).fetchall()
            else:
                rows = conn.execute("SELECT chunk_id,source_id,content,COALESCE(content_hash,'') content_hash FROM knowledge_chunks").fetchall()
            if not only_missing:
                try:
                    if tenant_id:
                        conn.execute("DELETE FROM knowledge_chunks_fts WHERE source_id IN (SELECT source_id FROM knowledge_sources WHERE tenant_id=?)", (tenant_id,))
                    else:
                        conn.execute("DELETE FROM knowledge_chunks_fts")
                except sqlite3.DatabaseError:
                    pass
            for row in rows:
                digest = _content_hash(row["content"])
                exists = conn.execute("SELECT content_hash FROM knowledge_embeddings WHERE chunk_id=?", (row["chunk_id"],)).fetchone()
                if not exists or exists["content_hash"] != digest:
                    emb = self.embedding_gateway.embed([row["content"]])
                    model_name = emb.model
                    vector = emb.vectors[0] if emb.vectors else _hash_embedding(row["content"])
                    conn.execute(
                        "INSERT OR REPLACE INTO knowledge_embeddings(chunk_id,source_id,embedding_model,embedding_version,vector_json,content_hash,provider,dimensions,warning,updated_at) VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                        (row["chunk_id"], row["source_id"], model_name, "1", json.dumps(vector), digest, emb.provider, emb.dimensions or len(vector), emb.warning),
                    )
                    conn.execute("UPDATE knowledge_chunks SET content_hash=?,embedding_model=? WHERE chunk_id=?", (digest, model_name, row["chunk_id"]))
                    indexed += 1
                if not only_missing:
                    try:
                        conn.execute("INSERT INTO knowledge_chunks_fts(chunk_id,source_id,content) VALUES(?,?,?)", (row["chunk_id"], row["source_id"], row["content"]))
                    except sqlite3.DatabaseError:
                        pass
                elif only_missing:
                    # FTS insert is best-effort; ignore duplicate errors.
                    try:
                        found = conn.execute("SELECT 1 FROM knowledge_chunks_fts WHERE chunk_id=? LIMIT 1", (row["chunk_id"],)).fetchone()
                        if not found:
                            conn.execute("INSERT INTO knowledge_chunks_fts(chunk_id,source_id,content) VALUES(?,?,?)", (row["chunk_id"], row["source_id"], row["content"]))
                    except sqlite3.DatabaseError:
                        pass
            conn.commit()
        return {"indexed": indexed, "embedding_model": self.embedding_gateway.model_name, "semantic_enabled": self.embedding_gateway.semantic_enabled}

    def _eligible_rows(self, *, scope: str, tenant_id: str, effective_year: str = "") -> list[sqlite3.Row]:
        sql = """SELECT c.chunk_id,c.source_id,c.chunk_index,c.content,s.title source_title,s.scope,s.tags,s.priority,s.authority,s.effective_year,s.category,
        e.vector_json,e.embedding_model,e.provider,e.dimensions,e.warning
        FROM knowledge_chunks c JOIN knowledge_sources s ON c.source_id=s.source_id
        LEFT JOIN knowledge_embeddings e ON e.chunk_id=c.chunk_id
        WHERE s.active=1 AND (s.scope=? OR s.scope='global') AND s.tenant_id IN (?,'global')"""
        params: list[object] = [scope, tenant_id]
        if effective_year:
            sql += " AND (s.effective_year=? OR s.effective_year='')"
            params.append(effective_year)
        with self._connect() as conn:
            return conn.execute(sql, tuple(params)).fetchall()

    def search_detailed(
        self,
        query: str,
        *,
        scope: str = "global",
        top_k: int = 5,
        tenant_id: str = "global",
        effective_year: str = "",
        lexical_weight: float = 0.45,
        vector_weight: float = 0.35,
        metadata_weight: float = 0.20,
    ) -> dict:
        terms = self._terms(query)
        inferred_year = effective_year or (re.search(r"20\d{2}", query).group(0) if re.search(r"20\d{2}", query) else "")
        rows = self._eligible_rows(scope=scope, tenant_id=tenant_id, effective_year=inferred_year)
        if not rows:
            return {"hits": [], "retrieval": {"mode": "hybrid", "effective_year": inferred_year, "warning": ""}}
        query_lower = query.lower()
        qemb = self.embedding_gateway.embed([query])
        query_vec = qemb.vectors[0] if qemb.vectors else _hash_embedding(query)
        portable_bm25 = {
            row["chunk_id"]: score
            for row, score in zip(rows, bm25_scores(query, [row["content"] for row in rows]))
        }

        # Best-effort FTS5 BM25 ranks. Lower bm25 is better, converted to a 0..1 score.
        bm25: dict[str, float] = {}
        if terms:
            fts_query = " OR ".join('"'+t.replace('"','')+'"' for t in terms[:18])
            try:
                with self._connect() as conn:
                    for r in conn.execute("SELECT chunk_id,bm25(knowledge_chunks_fts) rank FROM knowledge_chunks_fts WHERE knowledge_chunks_fts MATCH ? LIMIT 200", (fts_query,)).fetchall():
                        rank = abs(float(r["rank"] or 0.0))
                        bm25[r["chunk_id"]] = 1.0 / (1.0 + rank)
            except sqlite3.DatabaseError:
                bm25 = {}

        raw: list[dict] = []
        for row in rows:
            text = row["content"].lower()
            matched = 0.0
            unique = 0
            for term in terms:
                count = text.count(term)
                if count:
                    unique += 1
                    matched += (1.0 + math.log1p(count)) * min(len(term), 8)
            if query_lower and query_lower in text:
                matched += 20.0
            legacy_lex = matched * (1 + unique / max(len(terms), 1)) / max(math.sqrt(len(text) / 500), 0.8) if matched else 0.0
            lexical = max(
                bm25.get(row["chunk_id"], 0.0),
                portable_bm25.get(row["chunk_id"], 0.0),
                min(1.0, legacy_lex / 35.0),
            )
            try:
                vector = json.loads(row["vector_json"] or "[]")
            except Exception:
                vector = []
            vector_score = max(0.0, _cosine(query_vec, vector))
            authority = (row["authority"] or "internal").lower()
            authority_score = {"official": 1.0, "school": 0.88, "internal": 0.72, "public": 0.58}.get(authority, 0.62)
            priority_score = max(0.0, min(1.0, int(row["priority"] or 50) / 100.0))
            metadata_score = authority_score * 0.65 + priority_score * 0.35
            phrase_bonus = 0.08 if query_lower and query_lower in text else 0.0
            coverage = unique / max(1, len(terms)) if terms else 0.0
            rerank_bonus = min(0.12, coverage * 0.12)
            final = lexical_weight * lexical + vector_weight * vector_score + metadata_weight * metadata_score + phrase_bonus + rerank_bonus
            if lexical <= 0 and vector_score < 0.08:
                continue
            raw.append({
                "row": row, "score": final, "lexical": lexical, "vector": vector_score,
                "metadata": metadata_score, "coverage": coverage,
            })
        raw.sort(key=lambda x: x["score"], reverse=True)
        rerank_pool = raw[:max(50, top_k * 10)]
        reranked = self.reranker_gateway.rerank(
            query,
            [item["row"]["content"] for item in rerank_pool],
            top_n=max(top_k, min(len(rerank_pool), top_k * 4)),
        )
        for index, item in enumerate(rerank_pool):
            reranker_score = reranked.scores[index] if index < len(reranked.scores) else 0.0
            item["reranker"] = reranker_score
            if reranked.active:
                item["score"] = item["score"] * 0.75 + reranker_score * 0.25
        rerank_pool.sort(key=lambda x: x["score"], reverse=True)
        selected = rerank_pool[:top_k]
        hits = [SearchHit(
            source_id=x["row"]["source_id"], source_title=x["row"]["source_title"],
            chunk_id=x["row"]["chunk_id"], content=x["row"]["content"],
            score=round(x["score"], 4), chunk_index=int(x["row"]["chunk_index"]),
        ) for x in selected]

        # Conflict signal: same category has multiple non-empty years when query does not specify a year.
        years = sorted({str(r["effective_year"]) for r in rows if str(r["effective_year"] or "").strip()})
        warning = ""
        if not inferred_year and len(years) > 1:
            warning = f"检索范围包含多个有效年份（{', '.join(years[-4:])}）；涉及时效性规则时请指定年份。"
        if qemb.warning:
            warning = (warning + " " + qemb.warning).strip()
        breakdown = [{
            "chunk_id": x["row"]["chunk_id"], "source_id": x["row"]["source_id"],
            "score": round(x["score"], 4), "lexical": round(x["lexical"], 4),
            "vector": round(x["vector"], 4), "metadata": round(x["metadata"], 4),
            "reranker": round(x.get("reranker", 0.0), 4),
            "effective_year": x["row"]["effective_year"], "authority": x["row"]["authority"],
            "source_title": x["row"]["source_title"],
        } for x in selected]
        return {
            "hits": hits,
            "breakdown": breakdown,
            "retrieval": {
                "mode": "hybrid",
                "bm25": True,
                "bm25_backend": "sqlite_fts5+okapi" if bm25 else "okapi",
                "vector_backend": qemb.model,
                "semantic_embedding": qemb.provider != "local_hash" and self.embedding_gateway.semantic_enabled,
                "embedding_provider": qemb.provider,
                "embedding_model": qemb.model,
                "reranker_active": reranked.active,
                "reranker_provider": reranked.provider,
                "reranker_model": reranked.model,
                "reranker_warning": reranked.warning,
                "effective_year": inferred_year,
                "warning": warning,
                "note": ("已启用并成功使用远程语义 Embedding Provider。" if (qemb.provider != "local_hash" and self.embedding_gateway.semantic_enabled) else "当前检索使用 local-hash-v1 离线确定性向量通道，不等同于生产级语义 Embedding。远程 Provider 配置或调用失败时会显式降级。"),
            },
        }

    def search(self, query: str, *, scope: str = "global", top_k: int = 5, tenant_id: str = "global", effective_year: str = "") -> list[SearchHit]:
        return self.search_detailed(query, scope=scope, top_k=top_k, tenant_id=tenant_id, effective_year=effective_year)["hits"]

    def build_context(self, query: str, *, scope: str = "global", top_k: int = 5, max_chars: int = 9000, tenant_id: str = "global") -> tuple[str, list[KnowledgeRef]]:
        hits = self.search(query, scope=scope, top_k=top_k, tenant_id=tenant_id)
        blocks: list[str] = []
        refs: list[KnowledgeRef] = []
        used = 0
        for hit in hits:
            room = max_chars - used
            if room <= 0:
                break
            excerpt = hit.content[:room]
            marker = f"[KB:{hit.source_title}#{hit.chunk_index + 1}]"
            blocks.append(f"{marker}\n{excerpt}")
            used += len(excerpt)
            refs.append(KnowledgeRef(
                source_id=hit.source_id,
                title=hit.source_title,
                chunk_id=hit.chunk_id,
                score=hit.score,
                excerpt=excerpt[:260],
            ))
        return "\n\n".join(blocks), refs
