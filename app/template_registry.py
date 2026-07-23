from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TemplateRegistryError(ValueError):
    pass


class TemplateRegistry:
    """Tenant-scoped configurable workflow/artifact template registry.

    This registry uses SQLAlchemy directly so the same code works with SQLite and PostgreSQL. It
    never creates schema at runtime; Alembic / the central schema manifest own DDL.
    """

    def __init__(self, engine: Engine):
        self.engine = engine

    @staticmethod
    def _validate_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(steps, list) or not steps:
            raise TemplateRegistryError("workflow template requires at least one step")
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for idx, raw in enumerate(steps, 1):
            sid = str(raw.get("step_id") or raw.get("id") or "").strip()
            label = str(raw.get("label") or "").strip()
            if not sid or not label:
                raise TemplateRegistryError("each workflow step requires step_id and label")
            if sid in seen:
                raise TemplateRegistryError(f"duplicate workflow step_id: {sid}")
            seen.add(sid)
            out.append({
                "step_id": sid,
                "index": idx,
                "label": label,
                "description": str(raw.get("description") or "").strip(),
                "required_evidence": bool(raw.get("required_evidence", False)),
                "required_artifact": str(raw.get("required_artifact") or "").strip(),
            })
        return out

    def list_workflows(self, *, tenant_id: str, preset_id: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM workflow_template_definitions WHERE tenant_id=:tenant"
        params: dict[str, Any] = {"tenant": tenant_id}
        if preset_id:
            sql += " AND preset_id=:preset"
            params["preset"] = preset_id
        sql += " ORDER BY preset_id,status DESC,version DESC,created_at DESC"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [self._decode_workflow(dict(r)) for r in rows]

    def create_workflow(self, *, tenant_id: str, preset_id: str, name: str, steps: list[dict[str, Any]], created_by: str = "") -> dict[str, Any]:
        clean_steps = self._validate_steps(steps)
        template_id = f"WFT-{uuid4().hex[:14].upper()}"
        with self.engine.begin() as conn:
            version = conn.execute(text(
                "SELECT COALESCE(MAX(version),0)+1 AS v FROM workflow_template_definitions WHERE tenant_id=:tenant AND preset_id=:preset"
            ), {"tenant": tenant_id, "preset": preset_id}).mappings().first()["v"]
            conn.execute(text("""INSERT INTO workflow_template_definitions(
                template_id,tenant_id,preset_id,name,version,status,definition_json,created_by,created_at,updated_at
            ) VALUES(:id,:tenant,:preset,:name,:version,'draft',:definition,:by,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""), {
                "id": template_id, "tenant": tenant_id, "preset": preset_id, "name": name.strip() or "Custom Workflow",
                "version": int(version), "definition": json.dumps({"steps": clean_steps}, ensure_ascii=False), "by": created_by,
            })
        return self.get_workflow(template_id, tenant_id=tenant_id)

    def update_workflow(self, template_id: str, *, tenant_id: str, name: str | None = None, steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        current = self.get_workflow(template_id, tenant_id=tenant_id)
        if current["status"] == "active":
            raise TemplateRegistryError("active workflow templates are immutable; clone a new version instead")
        definition = current["definition"]
        if steps is not None:
            definition = {"steps": self._validate_steps(steps)}
        with self.engine.begin() as conn:
            conn.execute(text("""UPDATE workflow_template_definitions SET name=:name,definition_json=:definition,updated_at=CURRENT_TIMESTAMP
            WHERE template_id=:id AND tenant_id=:tenant"""), {
                "name": (name if name is not None else current["name"]).strip() or current["name"],
                "definition": json.dumps(definition, ensure_ascii=False), "id": template_id, "tenant": tenant_id,
            })
        return self.get_workflow(template_id, tenant_id=tenant_id)

    def activate_workflow(self, template_id: str, *, tenant_id: str) -> dict[str, Any]:
        target = self.get_workflow(template_id, tenant_id=tenant_id)
        with self.engine.begin() as conn:
            conn.execute(text("""UPDATE workflow_template_definitions SET status='archived',updated_at=CURRENT_TIMESTAMP
            WHERE tenant_id=:tenant AND preset_id=:preset AND status='active' AND template_id<>:id"""), {
                "tenant": tenant_id, "preset": target["preset_id"], "id": template_id,
            })
            conn.execute(text("""UPDATE workflow_template_definitions SET status='active',updated_at=CURRENT_TIMESTAMP
            WHERE tenant_id=:tenant AND template_id=:id"""), {"tenant": tenant_id, "id": template_id})
        return self.get_workflow(template_id, tenant_id=tenant_id)

    def get_workflow(self, template_id: str, *, tenant_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM workflow_template_definitions WHERE template_id=:id AND tenant_id=:tenant"), {
                "id": template_id, "tenant": tenant_id,
            }).mappings().first()
        if not row:
            raise KeyError(template_id)
        return self._decode_workflow(dict(row))

    def active_workflow(self, *, tenant_id: str, preset_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(text("""SELECT * FROM workflow_template_definitions
            WHERE tenant_id=:tenant AND preset_id=:preset AND status='active'
            ORDER BY version DESC,updated_at DESC LIMIT 1"""), {"tenant": tenant_id, "preset": preset_id}).mappings().first()
        return self._decode_workflow(dict(row)) if row else None

    @staticmethod
    def _decode_workflow(row: dict[str, Any]) -> dict[str, Any]:
        try:
            definition = json.loads(row.pop("definition_json") or "{}")
        except Exception:
            definition = {}
        row["definition"] = definition
        row["steps"] = list(definition.get("steps") or [])
        return row

    def list_artifacts(self, *, tenant_id: str, preset_id: str = "") -> list[dict[str, Any]]:
        sql = "SELECT * FROM artifact_template_definitions WHERE tenant_id=:tenant"
        params: dict[str, Any] = {"tenant": tenant_id}
        if preset_id:
            sql += " AND (presets_json LIKE :needle OR presets_json='[]')"
            params["needle"] = f'%"{preset_id}"%'
        sql += " ORDER BY status DESC,version DESC,created_at DESC"
        with self.engine.connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        return [self._decode_artifact(dict(r)) for r in rows]

    def create_artifact(self, *, tenant_id: str, kind: str, label: str, aliases: list[str] | None = None,
                        renderer: str = "structured_text", review_rubric: str = "general_v1",
                        presets: list[str] | None = None, schema: dict[str, Any] | None = None, created_by: str = "") -> dict[str, Any]:
        kind = kind.strip().lower()
        if not kind or not label.strip():
            raise TemplateRegistryError("artifact template requires kind and label")
        template_id = f"AFT-{uuid4().hex[:14].upper()}"
        with self.engine.begin() as conn:
            version = conn.execute(text(
                "SELECT COALESCE(MAX(version),0)+1 AS v FROM artifact_template_definitions WHERE tenant_id=:tenant AND kind=:kind"
            ), {"tenant": tenant_id, "kind": kind}).mappings().first()["v"]
            conn.execute(text("""INSERT INTO artifact_template_definitions(
                template_id,tenant_id,kind,label,version,status,aliases_json,schema_json,renderer,review_rubric,presets_json,created_by,created_at,updated_at
            ) VALUES(:id,:tenant,:kind,:label,:version,'draft',:aliases,:schema,:renderer,:rubric,:presets,:by,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"""), {
                "id": template_id, "tenant": tenant_id, "kind": kind, "label": label.strip(), "version": int(version),
                "aliases": json.dumps(list(dict.fromkeys([kind] + list(aliases or []))), ensure_ascii=False),
                "schema": json.dumps(schema or {}, ensure_ascii=False), "renderer": renderer.strip() or "structured_text",
                "rubric": review_rubric.strip() or "general_v1", "presets": json.dumps(list(dict.fromkeys(presets or [])), ensure_ascii=False),
                "by": created_by,
            })
        return self.get_artifact(template_id, tenant_id=tenant_id)

    def update_artifact(self, template_id: str, *, tenant_id: str, label: str | None = None, aliases: list[str] | None = None,
                        renderer: str | None = None, review_rubric: str | None = None, presets: list[str] | None = None,
                        schema: dict[str, Any] | None = None) -> dict[str, Any]:
        current = self.get_artifact(template_id, tenant_id=tenant_id)
        if current["status"] == "active":
            raise TemplateRegistryError("active artifact templates are immutable; create a new version instead")
        values = {
            "label": (label if label is not None else current["label"]).strip() or current["label"],
            "aliases": json.dumps(list(dict.fromkeys([current["kind"]] + list(aliases if aliases is not None else current.get("aliases", [])))), ensure_ascii=False),
            "renderer": (renderer if renderer is not None else current["renderer"]).strip() or current["renderer"],
            "rubric": (review_rubric if review_rubric is not None else current["review_rubric"]).strip() or current["review_rubric"],
            "presets": json.dumps(list(dict.fromkeys(presets if presets is not None else current.get("presets", []))), ensure_ascii=False),
            "schema": json.dumps(schema if schema is not None else current.get("schema", {}), ensure_ascii=False),
            "id": template_id, "tenant": tenant_id,
        }
        with self.engine.begin() as conn:
            conn.execute(text("""UPDATE artifact_template_definitions SET label=:label,aliases_json=:aliases,renderer=:renderer,
            review_rubric=:rubric,presets_json=:presets,schema_json=:schema,updated_at=CURRENT_TIMESTAMP
            WHERE template_id=:id AND tenant_id=:tenant"""), values)
        return self.get_artifact(template_id, tenant_id=tenant_id)

    def activate_artifact(self, template_id: str, *, tenant_id: str) -> dict[str, Any]:
        target = self.get_artifact(template_id, tenant_id=tenant_id)
        with self.engine.begin() as conn:
            conn.execute(text("""UPDATE artifact_template_definitions SET status='archived',updated_at=CURRENT_TIMESTAMP
            WHERE tenant_id=:tenant AND kind=:kind AND status='active' AND template_id<>:id"""), {
                "tenant": tenant_id, "kind": target["kind"], "id": template_id,
            })
            conn.execute(text("UPDATE artifact_template_definitions SET status='active',updated_at=CURRENT_TIMESTAMP WHERE tenant_id=:tenant AND template_id=:id"), {
                "tenant": tenant_id, "id": template_id,
            })
        return self.get_artifact(template_id, tenant_id=tenant_id)

    def get_artifact(self, template_id: str, *, tenant_id: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(text("SELECT * FROM artifact_template_definitions WHERE template_id=:id AND tenant_id=:tenant"), {
                "id": template_id, "tenant": tenant_id,
            }).mappings().first()
        if not row:
            raise KeyError(template_id)
        return self._decode_artifact(dict(row))

    def resolve_artifact(self, value: str | None, *, tenant_id: str, preset_id: str) -> dict[str, Any] | None:
        needle = (value or "").strip().lower()
        if not needle:
            return None
        for row in self.list_artifacts(tenant_id=tenant_id, preset_id=preset_id):
            if row["status"] != "active":
                continue
            aliases = {str(x).lower() for x in row.get("aliases", [])} | {row["kind"].lower(), row["template_id"].lower(), row["label"].lower()}
            if needle in aliases:
                return row
        return None

    @staticmethod
    def _decode_artifact(row: dict[str, Any]) -> dict[str, Any]:
        for src, dst, fallback in (("aliases_json", "aliases", []), ("schema_json", "schema", {}), ("presets_json", "presets", [])):
            try:
                row[dst] = json.loads(row.pop(src) or json.dumps(fallback))
            except Exception:
                row[dst] = fallback
        return row
