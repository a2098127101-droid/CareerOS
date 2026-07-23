"""Semantic RAG and evidence verification schema.

Fresh environments may already contain the portable columns/tables through the generated baseline
manifest. This migration is intentionally idempotent. PostgreSQL additionally enables pgvector and
adds a native vector column; SQLite continues to store portable vector_json for local compatibility.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0002_semantic_rag_pgvector"
down_revision = "0001_v10_baseline"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _tables() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables()
    if "knowledge_embeddings" in tables:
        cols = _columns("knowledge_embeddings")
        for name, col in [
            ("provider", sa.Column("provider", sa.Text(), nullable=False, server_default="local_hash")),
            ("dimensions", sa.Column("dimensions", sa.Integer(), nullable=False, server_default="0")),
            ("warning", sa.Column("warning", sa.Text(), nullable=False, server_default="")),
        ]:
            if name not in cols:
                op.add_column("knowledge_embeddings", col)
    if "evidence_claims" in tables:
        cols = _columns("evidence_claims")
        additions = [
            ("verification_status", sa.Column("verification_status", sa.Text(), nullable=False, server_default="UNVERIFIED")),
            ("verification_confidence", sa.Column("verification_confidence", sa.Float(), nullable=False, server_default="0")),
            ("verified_by", sa.Column("verified_by", sa.Text(), nullable=False, server_default="")),
            ("verified_at", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True)),
        ]
        for name, col in additions:
            if name not in cols:
                op.add_column("evidence_claims", col)

    if "rag_eval_cases" not in tables:
        op.create_table(
            "rag_eval_cases",
            sa.Column("case_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False, server_default="global"),
            sa.Column("query", sa.Text(), nullable=False),
            sa.Column("scope", sa.Text(), nullable=False, server_default="global"),
            sa.Column("effective_year", sa.Text(), nullable=False, server_default=""),
            sa.Column("expected_source_id", sa.Text(), nullable=False, server_default=""),
            sa.Column("expected_authority", sa.Text(), nullable=False, server_default=""),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_rag_eval_cases_tenant", "rag_eval_cases", ["tenant_id", "active", "created_at"])
    if "rag_eval_runs" not in tables:
        op.create_table(
            "rag_eval_runs",
            sa.Column("run_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False, server_default="global"),
            sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("cases_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("embedding_model", sa.Text(), nullable=False, server_default=""),
            sa.Column("retrieval_mode", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_rag_eval_runs_tenant", "rag_eval_runs", ["tenant_id", "created_at"])

    if bind.dialect.name == "postgresql":
        bind.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        cols = _columns("knowledge_embeddings")
        if "embedding_vector" not in cols:
            bind.execute(text("ALTER TABLE knowledge_embeddings ADD COLUMN embedding_vector vector"))
        # An unconstrained vector column supports mixed embedding dimensions. A dimension-specific
        # ANN index must only be created after a tenant/model dimension is fixed; exact pgvector
        # distance search is used until then.


def downgrade() -> None:
    bind = op.get_bind()
    tables = _tables()
    if "rag_eval_runs" in tables:
        op.drop_table("rag_eval_runs")
    if "rag_eval_cases" in tables:
        op.drop_table("rag_eval_cases")
    if bind.dialect.name == "postgresql" and "knowledge_embeddings" in tables and "embedding_vector" in _columns("knowledge_embeddings"):
        bind.execute(text("ALTER TABLE knowledge_embeddings DROP COLUMN embedding_vector"))
    # Portable columns are retained on downgrade to avoid destructive loss of verification history.
