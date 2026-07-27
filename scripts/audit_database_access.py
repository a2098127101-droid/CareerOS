from __future__ import annotations

import sys
import argparse
from pathlib import Path as _BootstrapPath
_ROOT = _BootstrapPath(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import json
import re
from pathlib import Path

# These modules are the intentional SQLite compatibility repository implementations.
# New business modules must not add direct sqlite access.
LEGACY_SQLITE_MODULES = {
    "store.py", "auth_store.py", "artifact_store.py", "evidence_store.py", "evidence_graph.py",
    "workflow_store.py", "collaboration_store.py", "knowledge.py", "job_store.py", "model_store.py",
    "commercial_store.py", "storage.py", "migrations.py", "domain_intelligence.py", "unified_runtime_store.py",
}

# DDL is allowed only in the centralized SQLite migration layer. PostgreSQL DDL is owned by Alembic.
SQLITE_DDL_OWNER = "app/migrations.py"


def audit(root: Path) -> dict:
    hits = []
    ddl_violations = []
    for path in sorted((root / "app").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = str(path.relative_to(root)).replace("\\", "/")
        if re.search(r"\bsqlite3\.connect\b|\bimport sqlite3\b", text):
            hits.append({
                "file": rel,
                "legacy_expected": path.name in LEGACY_SQLITE_MODULES,
            })
        ddl_scan_text = text.replace("CREATE TABLE/CREATE INDEX", "")
        if rel != SQLITE_DDL_OWNER and re.search(r"\bCREATE\s+TABLE\b", ddl_scan_text, flags=re.IGNORECASE):
            ddl_violations.append(rel)

    unexpected = [x for x in hits if not x["legacy_expected"]]
    business_sqlite = [x for x in hits if x["file"] != SQLITE_DDL_OWNER]
    return {
        "direct_sqlite_modules": len(hits),
        "direct_sqlite_business_modules": len(business_sqlite),
        "files": hits,
        "unexpected": unexpected,
        "store_owned_ddl_violations": sorted(set(ddl_violations)),
        "schema_ownership": "CENTRALIZED" if not ddl_violations else "SPLIT",
        "status": "TRANSITION" if hits else "ABSTRACTED",
        "note": "Direct sqlite CRUD remains intentionally in local compatibility repositories; table DDL is centralized in migrations.py and PostgreSQL Alembic migrations.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Audit direct SQLite access and centralized schema ownership.")
    parser.add_argument("--json-out", default="", help="Optional output path for the JSON report.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = audit(root)
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    print(payload)
    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
    raise SystemExit(1 if result["unexpected"] or result["store_owned_ddl_violations"] else 0)
