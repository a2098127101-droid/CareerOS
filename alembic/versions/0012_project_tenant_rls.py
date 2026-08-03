"""Force tenant row-level security on project aggregate tables.

Revision ID: 0012_project_tenant_rls
Revises: 0011_project_mvp_foundation
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0012_project_tenant_rls"
down_revision = "0011_project_mvp_foundation"
branch_labels = None
depends_on = None

PROJECT_RLS_TABLES = (
    "project_templates",
    "project_template_versions",
    "project_instances",
    "project_answers",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    tables = set(sa.inspect(bind).get_table_names())
    for table in PROJECT_RLS_TABLES:
        if table not in tables:
            raise RuntimeError(f"project RLS target table is missing: {table}")
        policy = f"tenant_isolation_{table}"
        op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
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


def downgrade() -> None:
    # Forward-only security migration. Removing FORCE RLS is not a safe downgrade.
    pass
