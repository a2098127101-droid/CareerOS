from __future__ import annotations

import json
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(x):.10g}" for x in vector) + "]"


def pgvector_capabilities(engine: Engine) -> dict:
    if engine.dialect.name != "postgresql":
        return {"postgresql": False, "extension": False, "column": False, "ready": False}
    extension = False
    column = False
    try:
        with engine.connect() as conn:
            extension = bool(conn.execute(text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")).scalar())
        cols = {c["name"] for c in inspect(engine).get_columns("knowledge_embeddings")}
        column = "embedding_vector" in cols
    except Exception:
        pass
    return {"postgresql": True, "extension": extension, "column": column, "ready": extension and column}


def upsert_pgvector(conn, *, chunk_id: str, vector: list[float]) -> bool:
    if not vector:
        return False
    try:
        conn.execute(
            text("UPDATE knowledge_embeddings SET embedding_vector=CAST(:vector AS vector) WHERE chunk_id=:chunk_id"),
            {"vector": vector_literal(vector), "chunk_id": chunk_id},
        )
        return True
    except Exception:
        return False


def search_pgvector(
    engine: Engine,
    *,
    query_vector: list[float],
    scope: str,
    tenant_id: str,
    effective_year: str = "",
    limit: int = 100,
) -> list[dict]:
    if not query_vector or not pgvector_capabilities(engine)["ready"]:
        return []
    sql = """
    SELECT c.chunk_id,c.source_id,c.chunk_index,c.content,
           s.title AS source_title,s.scope,s.tags,s.priority,s.authority,s.effective_year,s.category,
           e.embedding_model,e.provider,e.dimensions,
           GREATEST(0.0, 1.0 - (e.embedding_vector <=> CAST(:query_vector AS vector))) AS vector_score
    FROM knowledge_embeddings e
    JOIN knowledge_chunks c ON c.chunk_id=e.chunk_id
    JOIN knowledge_sources s ON s.source_id=c.source_id
    WHERE s.active=1
      AND (s.scope=:scope OR s.scope='global')
      AND s.tenant_id IN (:tenant,'global')
      AND e.embedding_vector IS NOT NULL
    """
    params = {"query_vector": vector_literal(query_vector), "scope": scope, "tenant": tenant_id, "limit": int(limit)}
    if effective_year:
        sql += " AND (s.effective_year=:year OR s.effective_year='')"
        params["year"] = effective_year
    sql += " ORDER BY e.embedding_vector <=> CAST(:query_vector AS vector) LIMIT :limit"
    with engine.connect() as conn:
        return [dict(r) for r in conn.execute(text(sql), params).mappings().all()]
