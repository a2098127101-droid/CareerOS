from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
_ROOT = _BootstrapPath(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import base64
import importlib.util
import json
import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import delete, insert

from app.core.database import BASELINE_METADATA, create_database_engine, load_schema_manifest


def decode(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"__bytes_b64__"}:
        return base64.b64decode(value["__bytes_b64__"])
    return value


def dependency_order() -> list[str]:
    manifest = load_schema_manifest()
    deps = {name: {fk["table"] for fk in spec.get("foreign_keys", []) if fk["table"] in manifest["tables"]} for name, spec in manifest["tables"].items()}
    order: list[str] = []
    pending = set(deps)
    while pending:
        ready = sorted([name for name in pending if not (deps[name] & pending)])
        if not ready:  # defensive fallback for cycles
            ready = [sorted(pending)[0]]
        for name in ready:
            order.append(name)
            pending.remove(name)
    return order


def validate_snapshot(snapshot_dir: Path) -> dict:
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "careeros-sqlite-snapshot-v1":
        raise ValueError("unsupported snapshot format")
    missing = [t for t, count in manifest.get("tables", {}).items() if int(count or 0) and not (snapshot_dir / f"{t}.jsonl").exists()]
    if missing:
        raise ValueError(f"missing table files: {missing}")
    corrupt = []
    for table, expected_hash in (manifest.get("sha256") or {}).items():
        file = snapshot_dir / f"{table}.jsonl"
        if not file.exists():
            continue
        actual = hashlib.sha256(file.read_bytes()).hexdigest()
        if expected_hash and actual != expected_hash:
            corrupt.append({"table": table, "expected": expected_hash, "actual": actual})
    if corrupt:
        raise ValueError(f"snapshot checksum mismatch: {corrupt[:3]}")
    return manifest


def import_snapshot(snapshot_dir: Path, database_url: str, *, truncate: bool = False, dry_run: bool = False) -> dict:
    source = validate_snapshot(snapshot_dir)
    order = dependency_order()
    if dry_run:
        return {"ok": True, "dry_run": True, "tables": source.get("tables", {}), "order": order}
    if not database_url.startswith(("postgresql://", "postgres://", "postgresql+")):
        raise ValueError("target must be PostgreSQL")
    if importlib.util.find_spec("psycopg") is None and importlib.util.find_spec("psycopg2") is None:
        raise RuntimeError("PostgreSQL driver missing. Install requirements-production.txt before importing.")

    engine = create_database_engine(database_url, "")
    inserted: dict[str, int] = {}
    with engine.begin() as conn:
        if truncate:
            for table_name in reversed(order):
                if table_name in BASELINE_METADATA.tables:
                    conn.execute(delete(BASELINE_METADATA.tables[table_name]))
        for table_name in order:
            table = BASELINE_METADATA.tables.get(table_name)
            file = snapshot_dir / f"{table_name}.jsonl"
            if table is None or not file.exists():
                continue
            count = 0
            batch: list[dict[str, Any]] = []
            for line in file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = {k: decode(v) for k, v in json.loads(line).items() if k in table.c}
                batch.append(row)
                if len(batch) >= 500:
                    conn.execute(insert(table), batch)
                    count += len(batch)
                    batch.clear()
            if batch:
                conn.execute(insert(table), batch)
                count += len(batch)
            inserted[table_name] = count
        # PostgreSQL SERIAL/IDENTITY sequences can lag behind imported explicit integer IDs.
        # Repair known integer primary-key sequences after data import.
        for table_name, pk in (("analytics_events", "event_id"), ("llm_usage", "id")):
            if table_name not in BASELINE_METADATA.tables:
                continue
            try:
                conn.exec_driver_sql(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}','{pk}'), COALESCE((SELECT MAX({pk}) FROM {table_name}), 1), true)"
                )
            except Exception:
                # Some schemas may use identity/no sequence; verification still catches row mismatches.
                pass
    return {"ok": True, "dry_run": False, "inserted": inserted}


def main() -> int:
    p = argparse.ArgumentParser(description="Import a CareerOS JSONL snapshot into a provisioned PostgreSQL database.")
    p.add_argument("--snapshot", required=True, type=Path)
    p.add_argument("--database-url", default="")
    p.add_argument("--truncate", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    result = import_snapshot(args.snapshot, args.database_url, truncate=args.truncate, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
