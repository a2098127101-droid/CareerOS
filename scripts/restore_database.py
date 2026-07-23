from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_manifest(backup: Path) -> dict:
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    if not manifest_path.is_file():
        raise RuntimeError("backup manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = sha256(backup)
    if actual != manifest.get("sha256"):
        raise RuntimeError("backup checksum mismatch")
    return manifest


def restore_sqlite(backup: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(backup)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close(); src.close()


def restore_postgres(backup: Path, database_url: str) -> None:
    binary = shutil.which("pg_restore")
    if not binary:
        raise RuntimeError("pg_restore is not installed; PostgreSQL restore NOT VERIFIED")
    subprocess.run([binary, "--clean", "--if-exists", "--no-owner", "--no-acl", "--dbname", database_url, str(backup)], check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a CareerOS backup after checksum verification. Destructive actions require --confirm.")
    parser.add_argument("--backup", required=True)
    parser.add_argument("--sqlite-target", default="")
    parser.add_argument("--database-url", default="")
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if not args.confirm:
        raise SystemExit("restore is destructive; pass --confirm after verifying the target")
    backup = Path(args.backup)
    manifest = verify_manifest(backup)
    if manifest.get("backend") == "sqlite":
        if not args.sqlite_target:
            raise SystemExit("--sqlite-target is required")
        restore_sqlite(backup, Path(args.sqlite_target))
    elif manifest.get("backend") == "postgresql":
        if not args.database_url:
            raise SystemExit("--database-url is required")
        restore_postgres(backup, args.database_url)
    else:
        raise RuntimeError("unsupported backup backend")
    print(json.dumps({"restored": True, "backend": manifest.get("backend"), "sha256": manifest.get("sha256")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
