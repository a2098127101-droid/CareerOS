"""billing sandbox and idempotent webhook foundation

Revision ID: 0005_billing_sandbox_foundation
Revises: 0004_model_governance_identity_privacy
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_billing_sandbox_foundation"
down_revision = "0004_model_governance_identity_privacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    tables = set(inspect(op.get_bind()).get_table_names())
    if "billing_orders" not in tables:
        op.create_table(
            "billing_orders",
            sa.Column("order_id", sa.Text(), primary_key=True),
            sa.Column("tenant_id", sa.Text(), nullable=False),
            sa.Column("plan_id", sa.Text(), nullable=False),
            sa.Column("provider", sa.Text(), nullable=False, server_default="mock"),
            sa.Column("external_order_id", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
            sa.Column("amount_minor", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("currency", sa.Text(), nullable=False, server_default="CNY"),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("idx_billing_orders_tenant", "billing_orders", ["tenant_id", "created_at"])
    if "billing_events" not in tables:
        op.create_table(
            "billing_events",
            sa.Column("event_id", sa.Text(), primary_key=True),
            sa.Column("provider", sa.Text(), nullable=False),
            sa.Column("event_key", sa.Text(), nullable=False),
            sa.Column("event_type", sa.Text(), nullable=False, server_default=""),
            sa.Column("tenant_id", sa.Text(), nullable=False, server_default=""),
            sa.Column("payload_hash", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.Text(), nullable=False, server_default="received"),
            sa.Column("result_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("received_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("processed_at", sa.DateTime()),
            sa.UniqueConstraint("provider", "event_key", name="uq_billing_event_provider_key"),
        )
        op.create_index("idx_billing_events_provider", "billing_events", ["provider", "received_at"])
        op.create_index("idx_billing_events_tenant", "billing_events", ["tenant_id", "received_at"])


def downgrade() -> None:
    # Billing audit history is intentionally preserved by default. Operators may
    # explicitly remove these tables after export if a destructive downgrade is required.
    pass
