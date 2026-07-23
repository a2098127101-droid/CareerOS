from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
_ROOT = _BootstrapPath(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import json
import sqlite3
from pathlib import Path


def generate(db_path: Path, out_path: Path) -> dict:
    # During the staged v1 migration some legacy SQLite stores still own table creation.
    # Preserve tables already described by the checked-in manifest and refresh every table
    # visible in the inspected database. This prevents an incomplete migration-only fixture
    # from accidentally deleting valid schema definitions.
    manifest = {"version": "1.0-beta1", "tables": {}}
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict) and isinstance(existing.get("tables"), dict):
                manifest["tables"].update(existing["tables"])
        except Exception:
            pass
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        tables = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        for table in tables:
            if table.startswith("knowledge_chunks_fts"):
                continue
            columns = []
            for row in conn.execute(f'PRAGMA table_info("{table}")'):
                default = row["dflt_value"]
                if row["name"] == "tenant_id" and default in {"'demo-school'", "'demo-org'"}:
                    default = None  # fresh v1 schemas must not silently assign a tenant
                columns.append({
                    "name": row["name"], "type": row["type"] or "TEXT", "notnull": bool(row["notnull"]),
                    "default": default, "pk": int(row["pk"]),
                })
            foreign_keys = [{
                "from": row["from"], "table": row["table"], "to": row["to"],
                "on_update": row["on_update"], "on_delete": row["on_delete"],
            } for row in conn.execute(f'PRAGMA foreign_key_list("{table}")')]
            indexes = []
            uniques = []
            for idx in conn.execute(f'PRAGMA index_list("{table}")'):
                name = idx["name"]
                cols = [x["name"] for x in conn.execute(f'PRAGMA index_info("{name}")') if x["name"]]
                if idx["unique"] and cols and cols not in uniques:
                    uniques.append(cols)
                if not name.startswith("sqlite_autoindex") and cols:
                    indexes.append({"name": name, "unique": bool(idx["unique"]), "columns": cols})
            manifest["tables"][table] = {
                "columns": columns, "foreign_keys": foreign_keys, "indexes": indexes,
                "unique_constraints": uniques,
            }
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the v1 baseline schema manifest from a migrated SQLite database.")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--out", default=Path("app/schema_manifest.json"), type=Path)
    args = parser.parse_args()
    manifest = generate(args.db, args.out)
    print(f"wrote {len(manifest['tables'])} tables to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
