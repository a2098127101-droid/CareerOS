"""Model governance, identity lifecycle and privacy foundation."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_model_governance_identity_privacy"
down_revision = "0003_runtime_infrastructure"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "llm_model_capabilities" not in tables:
        op.create_table(
            "llm_model_capabilities",
            sa.Column("provider_id", sa.Text(), nullable=False),
            sa.Column("model", sa.Text(), nullable=False),
            sa.Column("supports_streaming", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("supports_json_schema", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("supports_tools", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("supports_vision", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("supports_files", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("context_window", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_output", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reasoning_level", sa.Text(), nullable=False, server_default="none"),
            sa.Column("latency_class", sa.Text(), nullable=False, server_default="unknown"),
            sa.Column("input_cost_per_million", sa.Float(), nullable=False, server_default="0"),
            sa.Column("output_cost_per_million", sa.Float(), nullable=False, server_default="0"),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("provider_id", "model"),
        )
        op.create_index("idx_llm_model_capabilities_provider", "llm_model_capabilities", ["provider_id", "updated_at"])
    if "model_eval_runs" not in tables:
        op.create_table(
            "model_eval_runs",
            sa.Column("eval_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False, server_default="global"),
            sa.Column("task", sa.Text(), nullable=False, server_default="evaluation"),
            sa.Column("provider_id", sa.Text(), nullable=False),
            sa.Column("model", sa.Text(), nullable=False),
            sa.Column("metrics_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("cases_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_model_eval_runs_tenant", "model_eval_runs", ["tenant_id", "created_at"])
    if "user_invitations" not in tables:
        op.create_table(
            "user_invitations",
            sa.Column("invitation_id", sa.Text(), primary_key=True),
            sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("email", sa.Text(), nullable=False),
            sa.Column("role", sa.Text(), nullable=False),
            sa.Column("display_name", sa.Text(), nullable=False, server_default=""),
            sa.Column("invited_by", sa.Text(), nullable=False, server_default=""),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted_at", sa.DateTime(timezone=True)),
            sa.Column("revoked_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_user_invitations_tenant", "user_invitations", ["tenant_id", "created_at"])
        op.create_index("idx_user_invitations_email", "user_invitations", ["email", "tenant_id"])
    if "privacy_consents" not in tables:
        op.create_table(
            "privacy_consents",
            sa.Column("consent_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Text(), nullable=False),
            sa.Column("policy_version", sa.Text(), nullable=False),
            sa.Column("purpose", sa.Text(), nullable=False, server_default="service"),
            sa.Column("granted", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("source", sa.Text(), nullable=False, server_default="ui"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_privacy_consents_user", "privacy_consents", ["tenant_id", "user_id", "created_at"])
    if "data_subject_requests" not in tables:
        op.create_table(
            "data_subject_requests",
            sa.Column("request_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("user_id", sa.Text(), nullable=False),
            sa.Column("request_type", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("processed_at", sa.DateTime(timezone=True)),
        )
        op.create_index("idx_data_subject_requests_user", "data_subject_requests", ["tenant_id", "user_id", "created_at"])


def downgrade() -> None:
    # Identity/privacy audit history is intentionally retained to avoid destructive loss.
    pass
