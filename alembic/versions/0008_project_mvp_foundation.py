"""project mvp aggregate foundation

Revision ID: 0008_project_mvp_foundation
Revises: 0007_tenant_templates_evidence_risk
"""
from alembic import op
import sqlalchemy as sa


revision = "0008_project_mvp_foundation"
down_revision = "0007_tenant_templates_evidence_risk"
branch_labels = None
depends_on = None


def _install_immutability(bind) -> None:
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION reject_project_template_version_mutation()
            RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'project template versions are immutable';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute("DROP TRIGGER IF EXISTS trg_project_template_versions_immutable ON project_template_versions")
        op.execute(
            """
            CREATE TRIGGER trg_project_template_versions_immutable
            BEFORE UPDATE OR DELETE ON project_template_versions
            FOR EACH ROW EXECUTE FUNCTION reject_project_template_version_mutation()
            """
        )
        op.execute(
            """
            CREATE OR REPLACE FUNCTION enforce_project_tenant_scope()
            RETURNS trigger AS $$
            BEGIN
              IF TG_TABLE_NAME = 'project_template_versions' AND NOT EXISTS (
                SELECT 1 FROM project_templates
                WHERE template_id=NEW.template_id AND tenant_id=NEW.tenant_id
              ) THEN
                RAISE EXCEPTION 'project template version tenant mismatch';
              ELSIF TG_TABLE_NAME = 'project_instances' AND (
                NOT EXISTS (
                  SELECT 1 FROM project_templates
                  WHERE template_id=NEW.template_id AND tenant_id=NEW.tenant_id
                ) OR NOT EXISTS (
                  SELECT 1 FROM project_template_versions
                  WHERE template_version_id=NEW.template_version_id
                    AND template_id=NEW.template_id AND tenant_id=NEW.tenant_id
                ) OR NOT EXISTS (
                  SELECT 1 FROM sessions
                  WHERE session_id=NEW.session_id AND tenant_id=NEW.tenant_id
                    AND student_user_id=NEW.owner_user_id
                )
              ) THEN
                RAISE EXCEPTION 'project instance tenant, owner or session mismatch';
              ELSIF TG_TABLE_NAME = 'project_answers' AND NOT EXISTS (
                SELECT 1 FROM project_instances
                WHERE project_id=NEW.project_id AND tenant_id=NEW.tenant_id
                  AND owner_user_id=NEW.owner_user_id
              ) THEN
                RAISE EXCEPTION 'project answer tenant or owner mismatch';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
        for table in ("project_template_versions", "project_instances", "project_answers"):
            trigger = f"trg_{table}_tenant_guard"
            op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
            op.execute(
                f"CREATE TRIGGER {trigger} BEFORE INSERT OR UPDATE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION enforce_project_tenant_scope()"
            )
    elif bind.dialect.name == "sqlite":
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_project_template_versions_immutable_update
            BEFORE UPDATE ON project_template_versions
            BEGIN SELECT RAISE(ABORT, 'project template versions are immutable'); END
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_project_template_versions_tenant_guard
            BEFORE INSERT ON project_template_versions
            WHEN NOT EXISTS (
              SELECT 1 FROM project_templates
              WHERE template_id=NEW.template_id AND tenant_id=NEW.tenant_id
            )
            BEGIN SELECT RAISE(ABORT, 'project template version tenant mismatch'); END
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_project_instances_tenant_guard
            BEFORE INSERT ON project_instances
            WHEN NOT EXISTS (
              SELECT 1 FROM project_templates
              WHERE template_id=NEW.template_id AND tenant_id=NEW.tenant_id
            ) OR NOT EXISTS (
              SELECT 1 FROM project_template_versions
              WHERE template_version_id=NEW.template_version_id
                AND template_id=NEW.template_id AND tenant_id=NEW.tenant_id
            ) OR NOT EXISTS (
              SELECT 1 FROM sessions
              WHERE session_id=NEW.session_id AND tenant_id=NEW.tenant_id
                AND student_user_id=NEW.owner_user_id
            )
            BEGIN SELECT RAISE(ABORT, 'project instance tenant, owner or session mismatch'); END
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_project_instances_tenant_guard_update
            BEFORE UPDATE ON project_instances
            WHEN NOT EXISTS (
              SELECT 1 FROM project_templates
              WHERE template_id=NEW.template_id AND tenant_id=NEW.tenant_id
            ) OR NOT EXISTS (
              SELECT 1 FROM project_template_versions
              WHERE template_version_id=NEW.template_version_id
                AND template_id=NEW.template_id AND tenant_id=NEW.tenant_id
            ) OR NOT EXISTS (
              SELECT 1 FROM sessions
              WHERE session_id=NEW.session_id AND tenant_id=NEW.tenant_id
                AND student_user_id=NEW.owner_user_id
            )
            BEGIN SELECT RAISE(ABORT, 'project instance tenant, owner or session mismatch'); END
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_project_answers_owner_guard
            BEFORE INSERT ON project_answers
            WHEN NOT EXISTS (
              SELECT 1 FROM project_instances
              WHERE project_id=NEW.project_id AND tenant_id=NEW.tenant_id
                AND owner_user_id=NEW.owner_user_id
            )
            BEGIN SELECT RAISE(ABORT, 'project answer tenant or owner mismatch'); END
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_project_answers_owner_guard_update
            BEFORE UPDATE ON project_answers
            WHEN NOT EXISTS (
              SELECT 1 FROM project_instances
              WHERE project_id=NEW.project_id AND tenant_id=NEW.tenant_id
                AND owner_user_id=NEW.owner_user_id
            )
            BEGIN SELECT RAISE(ABORT, 'project answer tenant or owner mismatch'); END
            """
        )
        op.execute(
            """
            CREATE TRIGGER IF NOT EXISTS trg_project_template_versions_immutable_delete
            BEFORE DELETE ON project_template_versions
            BEGIN SELECT RAISE(ABORT, 'project template versions are immutable'); END
            """
        )


def upgrade() -> None:
    bind = op.get_bind()
    expected = {
        "project_templates",
        "project_template_versions",
        "project_instances",
        "project_answers",
    }
    present = expected.intersection(sa.inspect(bind).get_table_names())
    if present:
        if present != expected:
            missing = ", ".join(sorted(expected - present))
            raise RuntimeError(f"partial project MVP schema detected; missing: {missing}")
        # Fresh environments receive current tables from manifest-driven revision 0001.
        _install_immutability(bind)
        return

    op.create_table(
        "project_templates",
        sa.Column("template_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False, server_default="career_planning"),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("current_version_id", sa.Text()),
        sa.Column("created_by", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.tenant_id"], ondelete="CASCADE"),
        sa.UniqueConstraint("template_id", "tenant_id", name="uq_project_templates_tenant"),
    )
    op.create_index(
        "idx_project_templates_tenant_status",
        "project_templates",
        ["tenant_id", "status", "updated_at"],
    )

    op.create_table(
        "project_template_versions",
        sa.Column("template_version_id", sa.Text(), primary_key=True),
        sa.Column("template_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("background", sa.Text(), nullable=False, server_default=""),
        sa.Column("objective", sa.Text(), nullable=False, server_default=""),
        sa.Column("applicable_users", sa.Text(), nullable=False, server_default=""),
        sa.Column("estimated_time_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("output_type", sa.Text(), nullable=False, server_default="career_report"),
        sa.Column("questions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("material_requirements_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("artifact_structure_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("rubric_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("workflow_template_id", sa.Text(), nullable=False),
        sa.Column("artifact_template_id", sa.Text(), nullable=False, server_default="career_report_v1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="published"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["template_id"], ["project_templates.template_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("template_id", "version", name="uq_project_template_versions_version"),
        sa.UniqueConstraint("template_version_id", "tenant_id", name="uq_project_template_versions_tenant"),
    )
    op.create_index(
        "idx_project_template_versions_tenant_template",
        "project_template_versions",
        ["tenant_id", "template_id", "version"],
    )

    op.create_table(
        "project_instances",
        sa.Column("project_id", sa.Text(), primary_key=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.Text(), nullable=False),
        sa.Column("template_id", sa.Text(), nullable=False),
        sa.Column("template_version_id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("current_step", sa.Text(), nullable=False, server_default="overview"),
        sa.Column("current_artifact_id", sa.Text()),
        sa.Column("current_artifact_version_id", sa.Text()),
        sa.Column("latest_score_run_id", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["template_id"], ["project_templates.template_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_version_id"], ["project_template_versions.template_version_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("project_id", "tenant_id", name="uq_project_instances_tenant"),
    )
    op.create_index(
        "idx_project_instances_tenant_owner_status",
        "project_instances",
        ["tenant_id", "owner_user_id", "status", "updated_at"],
    )
    op.create_index(
        "idx_project_instances_tenant_template",
        "project_instances",
        ["tenant_id", "template_version_id"],
    )

    op.create_table(
        "project_answers",
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.Text(), nullable=False),
        sa.Column("question_id", sa.Text(), nullable=False),
        sa.Column("answer_json", sa.Text(), nullable=False, server_default="null"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("project_id", "question_id", name="pk_project_answers"),
        sa.ForeignKeyConstraint(["project_id"], ["project_instances.project_id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_project_answers_tenant_owner_project",
        "project_answers",
        ["tenant_id", "owner_user_id", "project_id"],
    )

    _install_immutability(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table in ("project_template_versions", "project_instances", "project_answers"):
            op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_tenant_guard ON {table}")
        op.execute("DROP FUNCTION IF EXISTS enforce_project_tenant_scope()")
        op.execute("DROP TRIGGER IF EXISTS trg_project_template_versions_immutable ON project_template_versions")
        op.execute("DROP FUNCTION IF EXISTS reject_project_template_version_mutation()")
    elif bind.dialect.name == "sqlite":
        op.execute("DROP TRIGGER IF EXISTS trg_project_template_versions_immutable_update")
        op.execute("DROP TRIGGER IF EXISTS trg_project_template_versions_immutable_delete")
        op.execute("DROP TRIGGER IF EXISTS trg_project_template_versions_tenant_guard")
        op.execute("DROP TRIGGER IF EXISTS trg_project_instances_tenant_guard")
        op.execute("DROP TRIGGER IF EXISTS trg_project_instances_tenant_guard_update")
        op.execute("DROP TRIGGER IF EXISTS trg_project_answers_owner_guard")
        op.execute("DROP TRIGGER IF EXISTS trg_project_answers_owner_guard_update")
    op.drop_index("idx_project_answers_tenant_owner_project", table_name="project_answers")
    op.drop_table("project_answers")
    op.drop_index("idx_project_instances_tenant_template", table_name="project_instances")
    op.drop_index("idx_project_instances_tenant_owner_status", table_name="project_instances")
    op.drop_table("project_instances")
    op.drop_index("idx_project_template_versions_tenant_template", table_name="project_template_versions")
    op.drop_table("project_template_versions")
    op.drop_index("idx_project_templates_tenant_status", table_name="project_templates")
    op.drop_table("project_templates")
