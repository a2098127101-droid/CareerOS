"""CareerOS v1.4 canonical runtime consistency.

Revision ID: 0008_canonical_runtime_consistency
Revises: 0007_tenant_templates_evidence_risk
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0008_canonical_runtime_consistency"
down_revision = "0007_tenant_templates_evidence_risk"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables()

    if "unified_runtime_revisions" not in tables:
        op.create_table(
            "unified_runtime_revisions",
            sa.Column("tenant_id", sa.Text(), primary_key=True),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    if "unified_runtime_entities" in tables:
        cols = _columns("unified_runtime_entities")
        pk = sa.inspect(bind).get_pk_constraint("unified_runtime_entities").get("constrained_columns") or []
        desired_pk = ["tenant_id", "owner_user_id", "entity_type", "entity_id"]
        needs_rebuild = pk != desired_pk or not {"version", "revision", "updated_by"}.issubset(cols)
        if needs_rebuild:
            if "unified_runtime_entities_v14" in _tables():
                op.drop_table("unified_runtime_entities_v14")
            op.create_table(
                "unified_runtime_entities_v14",
                sa.Column("tenant_id", sa.Text(), nullable=False),
                sa.Column("owner_user_id", sa.Text(), nullable=False, server_default=""),
                sa.Column("entity_type", sa.Text(), nullable=False),
                sa.Column("entity_id", sa.Text(), nullable=False),
                sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
                sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
                sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
                sa.Column("updated_by", sa.Text(), nullable=False, server_default=""),
                sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
                sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
                sa.PrimaryKeyConstraint("tenant_id", "owner_user_id", "entity_type", "entity_id"),
            )
            version_expr = "COALESCE(version,1)" if "version" in cols else "1"
            revision_expr = "COALESCE(revision,0)" if "revision" in cols else "0"
            updated_by_expr = "COALESCE(updated_by,'')" if "updated_by" in cols else "''"
            op.execute(sa.text(f"""INSERT INTO unified_runtime_entities_v14
                (tenant_id,owner_user_id,entity_type,entity_id,payload_json,version,revision,updated_by,deleted_at,created_at,updated_at)
                SELECT tenant_id,COALESCE(owner_user_id,''),entity_type,entity_id,payload_json,
                       {version_expr},{revision_expr},{updated_by_expr},deleted_at,created_at,updated_at
                FROM unified_runtime_entities"""))
            op.drop_table("unified_runtime_entities")
            op.rename_table("unified_runtime_entities_v14", "unified_runtime_entities")
        indexes = {i["name"] for i in sa.inspect(bind).get_indexes("unified_runtime_entities")}
        if "idx_unified_runtime_tenant_type_revision" not in indexes:
            op.create_index("idx_unified_runtime_tenant_type_revision", "unified_runtime_entities", ["tenant_id", "entity_type", "revision"])
        if "idx_unified_runtime_owner" not in indexes:
            op.create_index("idx_unified_runtime_owner", "unified_runtime_entities", ["tenant_id", "owner_user_id", "entity_type", "revision"])

    # Canonical workspace lifecycle metadata.
    if "evidence_items" in tables:
        cols = _columns("evidence_items")
        additions = [
            ("metadata_json", sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}")),
            ("version", sa.Column("version", sa.Integer(), nullable=False, server_default="1")),
            ("updated_at", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"))),
            ("deleted_at", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)),
        ]
        for name, column in additions:
            if name not in cols:
                op.add_column("evidence_items", column)
        indexes = {i["name"] for i in sa.inspect(bind).get_indexes("evidence_items")}
        if "idx_evidence_owner_active" not in indexes:
            op.create_index("idx_evidence_owner_active", "evidence_items", ["tenant_id", "owner_user_id", "deleted_at", "updated_at"])

    if "artifact_series" in tables:
        # Legacy schema allowed only one artifact per (session_id, kind). Workspace mode needs
        # multiple independent resumes/reports, so remove that compatibility constraint.
        uniques = {u.get("name"): tuple(u.get("column_names") or []) for u in sa.inspect(bind).get_unique_constraints("artifact_series")}
        for name, columns in uniques.items():
            if name and columns == ("session_id", "kind"):
                op.drop_constraint(name, "artifact_series", type_="unique")
        cols = _columns("artifact_series")
        if "version" not in cols:
            op.add_column("artifact_series", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if "deleted_at" not in cols:
            op.add_column("artifact_series", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        indexes = {i["name"] for i in sa.inspect(bind).get_indexes("artifact_series")}
        if "idx_artifact_owner_active" not in indexes:
            op.create_index("idx_artifact_owner_active", "artifact_series", ["tenant_id", "owner_user_id", "deleted_at", "updated_at"])


    if "ai_tasks" in tables:
        cols = _columns("ai_tasks")
        if "version" not in cols:
            op.add_column("ai_tasks", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if "completed_at" not in cols:
            op.add_column("ai_tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    # Deliberately non-destructive. Removing owner isolation/version metadata can reintroduce data loss.
    pass
