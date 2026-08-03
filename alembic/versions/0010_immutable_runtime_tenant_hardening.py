"""Repair immutable runtime migrations and add tenant isolation hardening.

Revision ID: 0010_immutable_runtime_tenant_hardening
Revises: 0009_domain_intelligence_v15

The published 0007 migration must remain byte-for-byte compatible with the
v1.0-beta1 release. Earlier v1.5 candidates incorrectly added
``unified_runtime_entities`` to 0007. Existing databases that had already
applied the original 0007 would therefore skip that table while fresh
installations received it. This forward-only migration repairs both paths.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_immutable_runtime_tenant_hardening"
down_revision = "0009_domain_intelligence_v15"
branch_labels = None
depends_on = None


TENANT_INDEXES: dict[str, tuple[str, ...]] = {
    "artifact_versions": ("tenant_id", "artifact_id", "version"),
    "auth_sessions": ("tenant_id", "user_id", "expires_at"),
    "capability_versions": ("tenant_id", "capability_id", "version"),
    "career_gap_versions": ("tenant_id", "gap_id", "version"),
    "domain_claim_versions": ("tenant_id", "claim_id", "version"),
}

# Tables that carry tenant_id directly and contain tenant-private data.
# Global catalog rows use tenant_id='global' and remain readable only when the
# application explicitly selects that tenant or uses the privileged migration role.
RLS_TABLES = (
    "analytics_events",
    "artifact_series",
    "artifact_versions",
    "capabilities",
    "capability_assessments",
    "capability_assessment_evidence",
    "capability_taxonomies",
    "capability_versions",
    "career_gap_versions",
    "career_gaps",
    "claim_capability_links",
    "claim_evidence_links",
    "classes",
    "conversations",
    "domain_audit_events",
    "domain_claim_versions",
    "domain_claims",
    "evidence_claims",
    "evidence_graph_edges",
    "evidence_items",
    "evidence_item_verification_history",
    "evidence_verification_history",
    "job_requirement_capability_links",
    "job_requirement_versions",
    "job_requirements",
    "jobs",
    "knowledge_sources",
    "sessions",
    "teacher_feedback",
    "workflow_instances",
    "workflow_steps",
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _indexes(table: str) -> set[str]:
    return {str(item.get("name") or "") for item in sa.inspect(op.get_bind()).get_indexes(table)}


def _create_runtime_tables(tables: set[str]) -> None:
    if "unified_runtime_revisions" not in tables:
        op.create_table(
            "unified_runtime_revisions",
            sa.Column("tenant_id", sa.Text(), primary_key=True),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    if "unified_runtime_entities" not in tables:
        op.create_table(
            "unified_runtime_entities",
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
    indexes = _indexes("unified_runtime_entities")
    if "idx_unified_runtime_tenant_type_revision" not in indexes:
        op.create_index(
            "idx_unified_runtime_tenant_type_revision",
            "unified_runtime_entities",
            ["tenant_id", "entity_type", "revision"],
        )
    if "idx_unified_runtime_owner" not in indexes:
        op.create_index(
            "idx_unified_runtime_owner",
            "unified_runtime_entities",
            ["tenant_id", "owner_user_id", "entity_type", "revision"],
        )


def _add_tenant_indexes(tables: set[str]) -> None:
    for table, columns in TENANT_INDEXES.items():
        if table not in tables:
            continue
        name = f"idx_{table}_tenant"
        if name not in _indexes(table):
            op.create_index(name, table, list(columns))


def _enable_postgres_rls(tables: set[str]) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table in RLS_TABLES:
        if table not in tables:
            continue
        policy = f"tenant_isolation_{table}"
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
        # FORCE prevents the table owner used by smaller self-hosted deployments
        # from silently bypassing the policy. Migration/super-admin access must
        # explicitly set app.platform_admin=on.
        op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
        op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))
        op.execute(sa.text(
            f'CREATE POLICY "{policy}" ON "{table}" '
            "USING ("
            "current_setting('app.platform_admin', true) = 'on' OR "
            "tenant_id = 'global' OR "
            "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')"
            ") WITH CHECK ("
            "current_setting('app.platform_admin', true) = 'on' OR "
            "tenant_id = NULLIF(current_setting('app.tenant_id', true), '')"
            ")"
        ))


def upgrade() -> None:
    tables = _tables()
    _create_runtime_tables(tables)
    tables = _tables()
    _add_tenant_indexes(tables)
    _enable_postgres_rls(tables)


def downgrade() -> None:
    # Forward-only safety migration: dropping tenant indexes or RLS policies
    # would weaken isolation, and dropping runtime tables would destroy data.
    pass
