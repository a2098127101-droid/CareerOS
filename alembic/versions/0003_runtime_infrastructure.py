"""Runtime infrastructure schema for private file lifecycle."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_runtime_infrastructure"
down_revision = "0002_semantic_rag_pgvector"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "stored_objects" not in tables:
        return
    cols = _columns("stored_objects")
    for name, col in [
        ("status", sa.Column("status", sa.Text(), nullable=False, server_default="active")),
        ("scan_status", sa.Column("scan_status", sa.Text(), nullable=False, server_default="unknown")),
        ("deleted_at", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)),
    ]:
        if name not in cols:
            op.add_column("stored_objects", col)
    indexes = {i["name"] for i in inspect(op.get_bind()).get_indexes("stored_objects")}
    if "idx_stored_objects_status" not in indexes:
        op.create_index("idx_stored_objects_status", "stored_objects", ["tenant_id", "status", "created_at"])


def downgrade() -> None:
    # Keep lifecycle metadata on downgrade to avoid losing deletion/scan audit state.
    pass
