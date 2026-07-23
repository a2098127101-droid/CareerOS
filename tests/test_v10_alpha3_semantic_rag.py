from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.evidence_graph import EvidenceGraphStore
from app.evidence_verification import (
    EvidenceVerificationService,
    STATUS_CONTRADICTED,
    STATUS_PARTIAL,
    STATUS_SUPPORTED,
    STATUS_UNSUPPORTED,
    STATUS_UNVERIFIED,
)
from app.knowledge import KnowledgeStore
from app.migrations import migration_status, run_migrations
from app.rag_evaluation import RAGEvalCase, evaluate_rag


def test_migration_11_adds_semantic_rag_and_verification_schema(tmp_path: Path):
    db = tmp_path / "alpha3.db"
    run_migrations(str(db))
    status = migration_status(str(db))
    assert status["current"] >= 11
    with sqlite3.connect(db) as conn:
        emb_cols = {r[1] for r in conn.execute("PRAGMA table_info(knowledge_embeddings)")}
        claim_cols = {r[1] for r in conn.execute("PRAGMA table_info(evidence_claims)")}
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"provider", "dimensions", "warning"} <= emb_cols
    assert {"verification_status", "verification_confidence", "verified_by", "verified_at"} <= claim_cols
    assert {"rag_eval_cases", "rag_eval_runs"} <= tables


def test_evidence_verifier_is_conservative_and_numeric_aware():
    verifier = EvidenceVerificationService(EmbeddingGateway(EmbeddingConfig()))
    supported = verifier.verify(
        "Completed 12 structured interviews.",
        [{"evidence_id": "E1", "source_label": "Project", "content": "Completed 12 structured interviews and summarized the findings."}],
    )
    assert supported.status in {STATUS_SUPPORTED, STATUS_PARTIAL}
    contradicted = verifier.verify(
        "Completed 20 structured interviews.",
        [{"evidence_id": "E1", "source_label": "Project", "content": "Completed 12 structured interviews and summarized the findings."}],
    )
    assert contradicted.status in {STATUS_CONTRADICTED, STATUS_UNSUPPORTED, STATUS_PARTIAL}
    no_evidence = verifier.verify("Received a professional certification.", [])
    assert no_evidence.status == STATUS_UNSUPPORTED


def test_claim_verification_persists_in_graph(tmp_path: Path):
    db = tmp_path / "graph.db"
    graph = EvidenceGraphStore(str(db))
    traced = graph.trace_artifact_version(
        tenant_id="org-a",
        session_id="S-1",
        artifact_id="ART-1",
        version_id="VER-1",
        content="Completed 12 structured interviews.",
        evidence_items=[{"evidence_id": "E1", "source_label": "Project", "content": "Completed 12 structured interviews."}],
    )
    assert traced["claims"] == 1
    claims = graph.list_claims("S-1", tenant_id="org-a")
    assert len(claims) == 1
    updated = graph.update_claim_verification(
        claims[0]["claim_id"], tenant_id="org-a", status="SUPPORTED", confidence=0.93, verified_by="system-test"
    )
    assert updated["verification_status"] == "SUPPORTED"
    assert float(updated["verification_confidence"]) == 0.93


def test_rag_evaluation_metrics_are_deterministic(tmp_path: Path):
    db = tmp_path / "rag.db"
    store = KnowledgeStore(str(db), EmbeddingGateway(EmbeddingConfig()))
    source = store.ingest(
        title="Official Guidance 2026",
        filename="official.txt",
        mime_type="text/plain",
        text="The 2026 official guidance requires evidence-based planning and documented development actions.",
        tenant_id="org-a",
        authority="official",
        effective_year="2026",
        priority=100,
    )
    store.ingest(
        title="Public Note 2025",
        filename="public.txt",
        mime_type="text/plain",
        text="A 2025 public note discusses general planning ideas.",
        tenant_id="org-a",
        authority="public",
        effective_year="2025",
        priority=30,
    )
    report = evaluate_rag(
        store,
        [RAGEvalCase(
            query="2026 evidence-based planning guidance",
            expected_source_id=source["source_id"],
            expected_authority="official",
            expected_year="2026",
        )],
        tenant_id="org-a",
    )
    assert report["metrics"]["recall_at_5"] == 1.0
    assert report["metrics"]["temporal_accuracy"] == 1.0


def test_embedding_metadata_records_truthful_local_fallback(tmp_path: Path):
    db = tmp_path / "embedding.db"
    store = KnowledgeStore(str(db), EmbeddingGateway(EmbeddingConfig(provider="local_hash", dimensions=64)))
    store.ingest(title="Demo", filename="demo.txt", mime_type="text/plain", text="Generic career development evidence.")
    with sqlite3.connect(db) as conn:
        provider, dims, warning = conn.execute("SELECT provider,dimensions,warning FROM knowledge_embeddings LIMIT 1").fetchone()
    assert provider == "local_hash"
    assert dims == 64
    assert warning == ""


def test_pgvector_alembic_migration_is_present_and_truthful():
    text_value = Path("alembic/versions/0002_semantic_rag_pgvector.py").read_text(encoding="utf-8")
    assert "CREATE EXTENSION IF NOT EXISTS vector" in text_value
    assert "embedding_vector vector" in text_value
    assert "ANN index" in text_value or "dimension-specific" in text_value
