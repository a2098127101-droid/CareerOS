from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
_ROOT = _BootstrapPath(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import base64
import hashlib
import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.core.database import load_schema_manifest


def encode(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"__bytes_b64__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def export_snapshot(db_path: Path, out_dir: Path) -> dict:
    if not db_path.exists():
        raise FileNotFoundError(db_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_schema_manifest()
    table_names = list(manifest["tables"].keys())
    counts: dict[str, int] = {}
    files: dict[str, str] = {}

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table in table_names:
            if table not in existing:
                counts[table] = 0
                continue
            target = out_dir / f"{table}.jsonl"
            h = hashlib.sha256()
            count = 0
            with target.open("w", encoding="utf-8") as f:
                for row in conn.execute(f'SELECT * FROM "{table}"'):
                    payload = {k: encode(row[k]) for k in row.keys()}
                    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
                    f.write(line)
                    h.update(line.encode("utf-8"))
                    count += 1
            counts[table] = count
            files[table] = h.hexdigest()

    result = {
        "format": "careeros-sqlite-snapshot-v1",
        "source": str(db_path),
        "schema_manifest_version": manifest.get("version"),
        "tables": counts,
        "sha256": files,
    }
    (out_dir / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Export a CareerOS SQLite database into deterministic JSONL migration files.")
    p.add_argument("--db", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()
    result = export_snapshot(args.db, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
