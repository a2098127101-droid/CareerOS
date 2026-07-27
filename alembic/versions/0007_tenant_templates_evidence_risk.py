"""tenant templates and evidence risk governance

Revision ID: 0007_tenant_templates_evidence_risk
Revises: 0006_template_engine_foundation
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_tenant_templates_evidence_risk"
down_revision = "0006_template_engine_foundation"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {x["name"] for x in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    cols = _columns("evidence_claims")
    if "risk_level" not in cols:
        op.add_column("evidence_claims", sa.Column("risk_level", sa.Text(), nullable=False, server_default="normal"))
    if "requires_human_review" not in cols:
        op.add_column("evidence_claims", sa.Column("requires_human_review", sa.Integer(), nullable=False, server_default="0"))
    cols = _columns("evidence_verification_history")
    if "risk_level" not in cols:
        op.add_column("evidence_verification_history", sa.Column("risk_level", sa.Text(), nullable=False, server_default="normal"))
    if "requires_human_review" not in cols:
        op.add_column("evidence_verification_history", sa.Column("requires_human_review", sa.Integer(), nullable=False, server_default="0"))

    if "workflow_template_definitions" not in tables:
        op.create_table(
            "workflow_template_definitions",
            sa.Column("template_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("preset_id", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
            sa.Column("definition_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_by", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_workflow_template_defs_tenant", "workflow_template_definitions", ["tenant_id", "preset_id", "status", "version"])
    if "artifact_template_definitions" not in tables:
        op.create_table(
            "artifact_template_definitions",
            sa.Column("template_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("kind", sa.Text(), nullable=False),
            sa.Column("label", sa.Text(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
            sa.Column("aliases_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("schema_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("renderer", sa.Text(), nullable=False, server_default="structured_text"),
            sa.Column("review_rubric", sa.Text(), nullable=False, server_default="general_v1"),
            sa.Column("presets_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("created_by", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_artifact_template_defs_tenant", "artifact_template_definitions", ["tenant_id", "kind", "status", "version"])


def downgrade() -> None:
    op.drop_index("idx_artifact_template_defs_tenant", table_name="artifact_template_definitions")
    op.drop_table("artifact_template_definitions")
    op.drop_index("idx_workflow_template_defs_tenant", table_name="workflow_template_definitions")
    op.drop_table("workflow_template_definitions")
    # Conservative downgrade leaves additive evidence columns in place on SQLite-compatible deployments.
