from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def backup_sqlite(source: Path, output: Path) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(source)
    dst = sqlite3.connect(output)
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()
    return {"backend": "sqlite", "file": str(output), "size_bytes": output.stat().st_size, "sha256": sha256(output)}


def backup_postgres(database_url: str, output: Path) -> dict:
    binary = shutil.which("pg_dump")
    if not binary:
        raise RuntimeError("pg_dump is not installed; PostgreSQL backup NOT VERIFIED")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([binary, "--format=custom", "--no-owner", "--no-acl", "--file", str(output), database_url], check=True)
    return {"backend": "postgresql", "file": str(output), "size_bytes": output.stat().st_size, "sha256": sha256(output), "tool": binary}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a CareerOS database backup with checksum manifest.")
    parser.add_argument("--backend", choices=["sqlite", "postgresql"], required=True)
    parser.add_argument("--sqlite-path", default="data/agent.db")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    if args.backend == "sqlite":
        result = backup_sqlite(Path(args.sqlite_path), out)
    else:
        if not args.database_url:
            raise SystemExit("--database-url is required for PostgreSQL backup")
        result = backup_postgres(args.database_url, out)
    manifest = {
        "backup_version": "1.0-beta0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        **result,
    }
    manifest_path = out.with_suffix(out.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
