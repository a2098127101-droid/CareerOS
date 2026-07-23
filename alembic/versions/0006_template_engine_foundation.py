"""Workflow templates, job intelligence requirements and evidence verification history."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_template_engine_foundation"
down_revision = "0005_billing_sandbox_foundation"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _has_table(table: str) -> bool:
    return table in set(inspect(op.get_bind()).get_table_names())


def _has_index(table: str, index: str) -> bool:
    return index in {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    if not _has_column("workflow_instances", "template_id"):
        op.add_column("workflow_instances", sa.Column("template_id", sa.Text(), nullable=False, server_default="career_development_v1"))
    if not _has_index("workflow_instances", "idx_workflow_template"):
        op.create_index("idx_workflow_template", "workflow_instances", ["tenant_id", "template_id", "updated_at"], unique=False)

    if not _has_table("job_requirements"):
        op.create_table(
            "job_requirements",
            sa.Column("requirement_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("job_id", sa.Text(), nullable=False),
            sa.Column("category", sa.Text(), nullable=False, server_default="requirement"),
            sa.Column("requirement_text", sa.Text(), nullable=False),
            sa.Column("normalized_key", sa.Text(), nullable=False, server_default=""),
            sa.Column("importance", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("source_type", sa.Text(), nullable=False, server_default="derived"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_job_requirements_job", "job_requirements", ["tenant_id", "job_id", "importance"], unique=False)

    if not _has_table("evidence_verification_history"):
        op.create_table(
            "evidence_verification_history",
            sa.Column("verification_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("session_id", sa.Text(), nullable=False),
            sa.Column("claim_id", sa.Text(), nullable=False),
            sa.Column("previous_status", sa.Text(), nullable=False, server_default="UNVERIFIED"),
            sa.Column("new_status", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
            sa.Column("verifier_type", sa.Text(), nullable=False, server_default="ai"),
            sa.Column("verified_by", sa.Text(), nullable=False, server_default=""),
            sa.Column("reason", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_verification_history_claim", "evidence_verification_history", ["tenant_id", "claim_id", "created_at"], unique=False)
        op.create_index("idx_verification_history_session", "evidence_verification_history", ["tenant_id", "session_id", "created_at"], unique=False)


def downgrade() -> None:
    for idx, table in [
        ("idx_verification_history_session", "evidence_verification_history"),
        ("idx_verification_history_claim", "evidence_verification_history"),
        ("idx_job_requirements_job", "job_requirements"),
    ]:
        try:
            op.drop_index(idx, table_name=table)
        except Exception:
            pass
    if _has_table("evidence_verification_history"):
        op.drop_table("evidence_verification_history")
    if _has_table("job_requirements"):
        op.drop_table("job_requirements")
    try:
        op.drop_index("idx_workflow_template", table_name="workflow_instances")
    except Exception:
        pass
    if _has_column("workflow_instances", "template_id"):
        op.drop_column("workflow_instances", "template_id")
