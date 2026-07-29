from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
_ROOT = _BootstrapPath(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.database import BASELINE_METADATA

PROJECT_GUARD_DDL = """
CREATE OR REPLACE FUNCTION reject_project_template_version_mutation()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'project template versions are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_project_template_versions_immutable
BEFORE UPDATE OR DELETE ON project_template_versions
FOR EACH ROW EXECUTE FUNCTION reject_project_template_version_mutation();

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
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_project_template_versions_tenant_guard
BEFORE INSERT OR UPDATE ON project_template_versions
FOR EACH ROW EXECUTE FUNCTION enforce_project_tenant_scope();

CREATE TRIGGER trg_project_instances_tenant_guard
BEFORE INSERT OR UPDATE ON project_instances
FOR EACH ROW EXECUTE FUNCTION enforce_project_tenant_scope();

CREATE TRIGGER trg_project_answers_tenant_guard
BEFORE INSERT OR UPDATE ON project_answers
FOR EACH ROW EXECUTE FUNCTION enforce_project_tenant_scope();
"""


def generate() -> str:
    dialect = postgresql.dialect()
    parts = ["-- CareerOS v1.0-beta1 PostgreSQL baseline generated from schema_manifest.json", ""]
    for table in BASELINE_METADATA.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect)).rstrip() + ";")
        parts.append("")
    for table in BASELINE_METADATA.sorted_tables:
        for index in table.indexes:
            parts.append(str(CreateIndex(index).compile(dialect=dialect)).rstrip() + ";")
    parts.extend(["", PROJECT_GUARD_DDL.strip()])
    return "\n".join(parts).strip() + "\n"


if __name__ == "__main__":
    target = Path("deploy/postgresql_baseline.sql")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate(), encoding="utf-8")
    print(target)
