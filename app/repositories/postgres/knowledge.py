from __future__ import annotations

import hashlib
import json
import math
import re
from uuid import uuid4

from sqlalchemy import text as sql
from sqlalchemy.engine import Engine

from ...embedding_gateway import EmbeddingGateway, local_hash_embedding
from ...knowledge import SearchHit
from ...models import KnowledgeRef
from ...pgvector_backend import pgvector_capabilities, search_pgvector, upsert_pgvector
from ..sqlalchemy_common import SQLAlchemyRepo


def _content_hash(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return max(-1.0, min(1.0, dot / (na * nb)))


class PostgresKnowledgeRepository(SQLAlchemyRepo):
    def __init__(self, engine: Engine, embedding_gateway: EmbeddingGateway):
        super().__init__(engine)
        self.embedding_gateway = embedding_gateway

    @staticmethod
    def chunk_text(text_value: str, chunk_size: int = 1800, overlap: int = 180) -> list[str]:
        clean = re.sub(r"\r\n?", "\n", text_value).strip()
        if not clean:
            return []
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", clean) if p.strip()]
        if len(paragraphs) <= 1:
            paragraphs = [p.strip() for p in clean.split("\n") if p.strip()]
        chunks: list[str] = []
        buf = ""
        for paragraph in paragraphs:
            candidate = (buf + "\n" + paragraph).strip() if buf else paragraph
            if len(candidate) <= chunk_size:
                buf = candidate
                continue
            if buf:
                chunks.append(buf)
                buf = ((buf[-overlap:] if overlap else "") + "\n" + paragraph).strip()
            else:
                start = 0
                while start < len(paragraph):
                    end = min(len(paragraph), start + chunk_size)
                    chunks.append(paragraph[start:end])
                    start = max(end - overlap, start + 1)
                buf = ""
        if buf:
            chunks.append(buf)
        return [c for c in chunks if c.strip()]

    @staticmethod
    def _terms(query: str) -> list[str]:
        q = query.lower()
        english = re.findall(r"[a-z0-9_+-]{2,}", q)
        runs = re.findall(r"[\u4e00-\u9fff]{2,}", q)
        terms = english[:20]
        for run in runs[:12]:
            if len(run) <= 6:
                terms.append(run)
            terms.extend(run[i:i + 2] for i in range(max(0, len(run) - 1)))
        return list(dict.fromkeys(t for t in terms if t.strip()))[:60]

    def _store_embedding(self, conn, *, chunk_id: str, source_id: str, content: str) -> tuple[str, int, str]:
        result = self.embedding_gateway.embed([content])
        vector = result.vectors[0] if result.vectors else local_hash_embedding(content, self.embedding_gateway.config.dimensions)
        digest = _content_hash(content)
        conn.execute(
            sql(
                """INSERT INTO knowledge_embeddings(
                    chunk_id,source_id,embedding_model,embedding_version,vector_json,content_hash,provider,dimensions,warning
                ) VALUES(:chunk_id,:source_id,:model,'1',:vector,:hash,:provider,:dimensions,:warning)"""
            ),
            {
                "chunk_id": chunk_id,
                "source_id": source_id,
                "model": result.model,
                "vector": json.dumps(vector),
                "hash": digest,
                "provider": result.provider,
                "dimensions": result.dimensions or len(vector),
                "warning": result.warning,
            },
        )
        if pgvector_capabilities(self.engine)["ready"]:
            upsert_pgvector(conn, chunk_id=chunk_id, vector=vector)
        return result.model, result.dimensions or len(vector), result.warning

    def ingest(
        self,
        *,
        title,
        filename,
        mime_type,
        text: str,
        scope="global",
        tags=None,
        category="other",
        authority="internal",
        effective_year="",
        priority=50,
        tenant_id="global",
    ):
        chunks = self.chunk_text(text)
        source_id = str(uuid4())
        with self.engine.begin() as conn:
            conn.execute(
                sql(
                    """INSERT INTO knowledge_sources(
                        source_id,tenant_id,title,filename,mime_type,scope,tags,active,char_count,chunk_count,
                        category,authority,effective_year,priority
                    ) VALUES(:id,:tenant,:title,:filename,:mime,:scope,:tags,1,:chars,:chunks,:category,:authority,:year,:priority)"""
                ),
                {
                    "id": source_id,
                    "tenant": tenant_id,
                    "title": title,
                    "filename": filename,
                    "mime": mime_type,
                    "scope": scope,
                    "tags": json.dumps(tags or [], ensure_ascii=False),
                    "chars": len(text),
                    "chunks": len(chunks),
                    "category": category,
                    "authority": authority,
                    "year": effective_year,
                    "priority": int(priority),
                },
            )
            for idx, chunk in enumerate(chunks):
                chunk_id = str(uuid4())
                digest = _content_hash(chunk)
                conn.execute(
                    sql(
                        "INSERT INTO knowledge_chunks(chunk_id,source_id,chunk_index,content,content_hash,embedding_model) VALUES(:cid,:sid,:idx,:content,:hash,'')"
                    ),
                    {"cid": chunk_id, "sid": source_id, "idx": idx, "content": chunk, "hash": digest},
                )
                model, _, _ = self._store_embedding(conn, chunk_id=chunk_id, source_id=source_id, content=chunk)
                conn.execute(sql("UPDATE knowledge_chunks SET embedding_model=:model WHERE chunk_id=:id"), {"model": model, "id": chunk_id})
        return {
            "source_id": source_id,
            "tenant_id": tenant_id,
            "title": title,
            "chunk_count": len(chunks),
            "char_count": len(text),
            "scope": scope,
            "category": category,
            "authority": authority,
            "effective_year": effective_year,
            "priority": priority,
        }

    def list_sources(self, tenant_id=None):
        rows = self.all("SELECT * FROM knowledge_sources ORDER BY updated_at DESC") if tenant_id is None else self.all(
            "SELECT * FROM knowledge_sources WHERE tenant_id IN (:tenant,'global') ORDER BY updated_at DESC", {"tenant": tenant_id}
        )
        result = []
        for row in rows:
            item = dict(row)
            item["tags"] = json.loads(item.get("tags") or "[]")
            item["active"] = bool(item["active"])
            result.append(item)
        return result

    def update_source(self, source_id, *, title=None, scope=None, tags=None, active=None, category=None, authority=None, effective_year=None, priority=None, tenant_id=None):
        row = self.one("SELECT * FROM knowledge_sources WHERE source_id=:id", {"id": source_id})
        if not row:
            raise KeyError(source_id)
        if tenant_id is not None and row["tenant_id"] != tenant_id:
            raise KeyError(source_id)
        vals = dict(row)
        vals.update({
            "title": title if title is not None else row["title"],
            "scope": scope if scope is not None else row["scope"],
            "tags": json.dumps(tags, ensure_ascii=False) if tags is not None else row["tags"],
            "active": 1 if active else 0 if active is not None else row["active"],
            "category": category if category is not None else row["category"],
            "authority": authority if authority is not None else row["authority"],
            "effective_year": effective_year if effective_year is not None else row["effective_year"],
            "priority": int(priority) if priority is not None else row["priority"],
        })
        self.execute(
            """UPDATE knowledge_sources SET title=:title,scope=:scope,tags=:tags,active=:active,category=:category,
               authority=:authority,effective_year=:effective_year,priority=:priority,updated_at=CURRENT_TIMESTAMP WHERE source_id=:source_id""",
            {**vals, "source_id": source_id},
        )

    def delete_source(self, source_id, *, tenant_id=None):
        row = self.one("SELECT tenant_id FROM knowledge_sources WHERE source_id=:id", {"id": source_id})
        if not row or (tenant_id is not None and row["tenant_id"] != tenant_id):
            raise KeyError(source_id)
        with self.engine.begin() as conn:
            conn.execute(sql("DELETE FROM knowledge_embeddings WHERE source_id=:id"), {"id": source_id})
            conn.execute(sql("DELETE FROM knowledge_chunks WHERE source_id=:id"), {"id": source_id})
            conn.execute(sql("DELETE FROM knowledge_sources WHERE source_id=:id"), {"id": source_id})

    def rebuild_hybrid_index(self, *, only_missing=False, tenant_id=None):
        indexed = 0
        fallback_count = 0
        warnings: list[str] = []
        with self.engine.begin() as conn:
            if tenant_id:
                rows = conn.execute(sql("""SELECT c.chunk_id,c.source_id,c.content,COALESCE(c.content_hash,'') content_hash
                    FROM knowledge_chunks c JOIN knowledge_sources s ON s.source_id=c.source_id WHERE s.tenant_id=:tenant"""), {"tenant": tenant_id}).mappings().all()
            else:
                rows = conn.execute(sql("SELECT chunk_id,source_id,content,COALESCE(content_hash,'') content_hash FROM knowledge_chunks")).mappings().all()
            for row in rows:
                digest = _content_hash(row["content"])
                existing = conn.execute(sql("SELECT content_hash FROM knowledge_embeddings WHERE chunk_id=:id"), {"id": row["chunk_id"]}).mappings().first()
                if only_missing and existing and existing["content_hash"] == digest:
                    continue
                result = self.embedding_gateway.embed([row["content"]])
                vector = result.vectors[0] if result.vectors else local_hash_embedding(row["content"], self.embedding_gateway.config.dimensions)
                payload = {
                    "id": row["chunk_id"], "sid": row["source_id"], "model": result.model,
                    "vec": json.dumps(vector), "hash": digest, "provider": result.provider,
                    "dimensions": result.dimensions or len(vector), "warning": result.warning,
                }
                if existing:
                    conn.execute(sql("""UPDATE knowledge_embeddings SET embedding_model=:model,embedding_version='1',vector_json=:vec,
                        content_hash=:hash,provider=:provider,dimensions=:dimensions,warning=:warning,updated_at=CURRENT_TIMESTAMP WHERE chunk_id=:id"""), payload)
                else:
                    conn.execute(sql("""INSERT INTO knowledge_embeddings(chunk_id,source_id,embedding_model,embedding_version,vector_json,content_hash,provider,dimensions,warning)
                        VALUES(:id,:sid,:model,'1',:vec,:hash,:provider,:dimensions,:warning)"""), payload)
                conn.execute(sql("UPDATE knowledge_chunks SET content_hash=:hash,embedding_model=:model WHERE chunk_id=:id"), payload)
                if result.provider == "local_hash":
                    fallback_count += 1
                if result.warning:
                    warnings.append(result.warning)
                if pgvector_capabilities(self.engine)["ready"]:
                    upsert_pgvector(conn, chunk_id=row["chunk_id"], vector=vector)
                indexed += 1
        return {
            "indexed": indexed,
            "embedding_model": self.embedding_gateway.model_name,
            "semantic_enabled": self.embedding_gateway.semantic_enabled,
            "fallback_count": fallback_count,
            "warnings": list(dict.fromkeys(warnings))[:10],
            "pgvector": pgvector_capabilities(self.engine),
        }

    def _eligible_rows(self, scope, tenant_id, effective_year=""):
        query = """SELECT c.chunk_id,c.source_id,c.chunk_index,c.content,s.title source_title,s.scope,s.tags,s.priority,s.authority,
            s.effective_year,s.category,e.vector_json,e.embedding_model,e.provider,e.dimensions,e.warning
            FROM knowledge_chunks c JOIN knowledge_sources s ON c.source_id=s.source_id
            LEFT JOIN knowledge_embeddings e ON e.chunk_id=c.chunk_id
            WHERE s.active=1 AND (s.scope=:scope OR s.scope='global') AND s.tenant_id IN (:tenant,'global')"""
        params = {"scope": scope, "tenant": tenant_id}
        if effective_year:
            query += " AND (s.effective_year=:year OR s.effective_year='')"
            params["year"] = effective_year
        return self.all(query, params)

    def search_detailed(self, query, *, scope="global", top_k=5, tenant_id="global", effective_year="", lexical_weight=.45, vector_weight=.35, metadata_weight=.2):
        terms = self._terms(query)
        match = re.search(r"20\d{2}", query)
        year = effective_year or (match.group(0) if match else "")
        qemb = self.embedding_gateway.embed([query])
        qvec = qemb.vectors[0] if qemb.vectors else local_hash_embedding(query, self.embedding_gateway.config.dimensions)
        pgvector = pgvector_capabilities(self.engine)
        vector_candidates = search_pgvector(
            self.engine, query_vector=qvec, scope=scope, tenant_id=tenant_id, effective_year=year, limit=max(100, top_k * 20)
        ) if pgvector["ready"] else []
        vector_by_chunk = {r["chunk_id"]: max(0.0, float(r.get("vector_score") or 0.0)) for r in vector_candidates}
        rows = self._eligible_rows(scope, tenant_id, year)
        if not rows:
            return {"hits": [], "breakdown": [], "retrieval": {"mode": "hybrid", "effective_year": year, "warning": ""}}
        query_lower = query.lower()
        raw = []
        for row in rows:
            txt = row["content"].lower()
            matched = 0.0
            unique = 0
            for term in terms:
                count = txt.count(term)
                if count:
                    unique += 1
                    matched += (1 + math.log1p(count)) * min(len(term), 8)
            if query_lower and query_lower in txt:
                matched += 20
            lexical = min(1.0, (matched * (1 + unique / max(len(terms), 1)) / max(math.sqrt(len(txt) / 500), .8)) / 35.0) if matched else 0.0
            if row["chunk_id"] in vector_by_chunk:
                vector_score = vector_by_chunk[row["chunk_id"]]
            else:
                try:
                    vector = json.loads(row["vector_json"] or "[]")
                except Exception:
                    vector = []
                vector_score = max(0.0, _cosine(qvec, vector))
            authority = {"official": 1.0, "school": .88, "internal": .72, "public": .58}.get((row["authority"] or "internal").lower(), .62)
            priority = max(0, min(1, int(row["priority"] or 50) / 100))
            metadata = authority * .65 + priority * .35
            coverage = unique / max(1, len(terms)) if terms else 0
            final = lexical_weight * lexical + vector_weight * vector_score + metadata_weight * metadata
            final += .08 if query_lower and query_lower in txt else 0
            final += min(.12, coverage * .12)
            if lexical <= 0 and vector_score < .08:
                continue
            raw.append({"row": row, "score": final, "lexical": lexical, "vector": vector_score, "metadata": metadata, "coverage": coverage})
        raw.sort(key=lambda x: x["score"], reverse=True)
        selected = raw[:top_k]
        hits = [SearchHit(
            source_id=x["row"]["source_id"], source_title=x["row"]["source_title"],
            chunk_id=x["row"]["chunk_id"], content=x["row"]["content"], score=round(x["score"], 4),
            chunk_index=int(x["row"]["chunk_index"]),
        ) for x in selected]
        years = sorted({str(r["effective_year"]) for r in rows if str(r["effective_year"] or "").strip()})
        warning = "" if year or len(years) <= 1 else f"检索范围包含多个有效年份（{', '.join(years[-4:])}）；涉及时效性规则时请指定年份。"
        if qemb.warning:
            warning = (warning + " " + qemb.warning).strip()
        mode = "pgvector_hybrid" if pgvector["ready"] else "portable_hybrid"
        return {
            "hits": hits,
            "breakdown": [{
                "chunk_id": x["row"]["chunk_id"], "source_id": x["row"]["source_id"],
                "score": round(x["score"], 4), "lexical": round(x["lexical"], 4), "vector": round(x["vector"], 4),
                "metadata": round(x["metadata"], 4), "effective_year": x["row"]["effective_year"], "authority": x["row"]["authority"],
                "embedding_provider": x["row"].get("provider", "") if hasattr(x["row"], "get") else "",
            } for x in selected],
            "retrieval": {
                "mode": mode,
                "bm25": False,
                "vector_backend": "pgvector" if pgvector["ready"] else self.embedding_gateway.model_name,
                "pgvector": pgvector,
                "semantic_embedding": qemb.provider != "local_hash" and self.embedding_gateway.semantic_enabled,
                "embedding_provider": qemb.provider,
                "embedding_model": qemb.model,
                "effective_year": year,
                "warning": warning,
                "note": (
                    "PostgreSQL pgvector exact distance search is active. ANN indexing requires a fixed embedding dimension and is not claimed in beta1."
                    if pgvector["ready"] else
                    "Portable vector_json exact scan is active. pgvector requires PostgreSQL migration 0002 and the vector extension."
                ),
            },
        }

    def search(self, query, *, scope="global", top_k=5, tenant_id="global", effective_year=""):
        return self.search_detailed(query, scope=scope, top_k=top_k, tenant_id=tenant_id, effective_year=effective_year)["hits"]

    def build_context(self, query, *, scope="global", top_k=5, max_chars=9000, tenant_id="global"):
        hits = self.search(query, scope=scope, top_k=top_k, tenant_id=tenant_id)
        blocks, refs, used = [], [], 0
        for hit in hits:
            room = max_chars - used
            if room <= 0:
                break
            excerpt = hit.content[:room]
            blocks.append(f"[KB:{hit.source_title}#{hit.chunk_index + 1}]\n{excerpt}")
            used += len(excerpt)
            refs.append(KnowledgeRef(source_id=hit.source_id, title=hit.source_title, chunk_id=hit.chunk_id, score=hit.score, excerpt=excerpt[:260]))
        return "\n\n".join(blocks), refs

    def stats(self, *, tenant_id="global") -> dict:
        row = self.one(
            "SELECT COUNT(*) sources,COALESCE(SUM(chunk_count),0) chunks FROM knowledge_sources WHERE active=1 AND tenant_id IN (:tenant,'global')",
            {"tenant": tenant_id},
        )
        return {"sources": int((row or {}).get("sources") or 0), "chunks": int((row or {}).get("chunks") or 0)}
