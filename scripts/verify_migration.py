from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
_ROOT = _BootstrapPath(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import json
from pathlib import Path

from sqlalchemy import func, select

from app.core.database import BASELINE_METADATA, create_database_engine
from scripts.import_snapshot_to_postgres import validate_snapshot


def verify(snapshot_dir: Path, database_url: str, db_path: str = "") -> dict:
    snapshot = validate_snapshot(snapshot_dir)
    engine = create_database_engine(database_url, db_path)
    mismatches = []
    actual = {}
    with engine.connect() as conn:
        for table_name, expected in snapshot.get("tables", {}).items():
            table = BASELINE_METADATA.tables.get(table_name)
            if table is None:
                continue
            count = int(conn.execute(select(func.count()).select_from(table)).scalar_one())
            actual[table_name] = count
            if count != int(expected or 0):
                mismatches.append({"table": table_name, "expected": int(expected or 0), "actual": count})
    return {"ok": not mismatches, "mismatches": mismatches, "counts": actual}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--snapshot", required=True, type=Path)
    p.add_argument("--database-url", default="")
    p.add_argument("--db-path", default="")
    args = p.parse_args()
    result = verify(args.snapshot, args.database_url, args.db_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
