from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from app.core.database import create_database_engine


def certify(database_url: str) -> dict:
    if not database_url.startswith(("postgresql://", "postgres://", "postgresql+")):
        return {"ok": False, "status": "NOT_CONFIGURED", "detail": "PostgreSQL DATABASE_URL is required"}
    pg_dump = shutil.which("pg_dump")
    pg_restore = shutil.which("pg_restore")
    if not pg_dump or not pg_restore:
        return {"ok": False, "status": "NOT_VERIFIED", "detail": "pg_dump/pg_restore are not installed", "pg_dump": bool(pg_dump), "pg_restore": bool(pg_restore)}
    schema = f"careeros_dr_{uuid4().hex[:10]}"
    marker = uuid4().hex
    engine = create_database_engine(database_url, "")
    with tempfile.TemporaryDirectory(prefix="careeros-dr-") as td:
        dump = Path(td) / "probe.dump"
        try:
            with engine.begin() as conn:
                conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                conn.execute(text(f'CREATE TABLE "{schema}".probe(id INTEGER PRIMARY KEY, marker TEXT NOT NULL)'))
                conn.execute(text(f'INSERT INTO "{schema}".probe(id, marker) VALUES (1, :marker)'), {"marker": marker})
            subprocess.run([pg_dump, "--dbname", database_url, "--format", "custom", "--schema", schema, "--file", str(dump)], check=True, capture_output=True, text=True)
            if not dump.exists() or dump.stat().st_size <= 0:
                raise RuntimeError("pg_dump did not produce a backup file")
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            subprocess.run([pg_restore, "--dbname", database_url, "--no-owner", str(dump)], check=True, capture_output=True, text=True)
            with engine.connect() as conn:
                restored = conn.execute(text(f'SELECT marker FROM "{schema}".probe WHERE id=1')).scalar_one()
            ok = restored == marker
            return {"ok": ok, "status": "PASS" if ok else "FAIL", "detail": "temporary-schema pg_dump/pg_restore round-trip succeeded" if ok else "restored marker mismatch", "schema": schema, "backup_bytes": dump.stat().st_size}
        except subprocess.CalledProcessError as exc:
            return {"ok": False, "status": "FAIL", "detail": (exc.stderr or exc.stdout or str(exc))[-2000:], "schema": schema}
        except Exception as exc:
            return {"ok": False, "status": "FAIL", "detail": str(exc), "schema": schema}
        finally:
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
            except Exception:
                pass
            engine.dispose()


def main() -> int:
    p = argparse.ArgumentParser(description="Non-destructive PostgreSQL disaster-recovery certification using a temporary schema.")
    p.add_argument("--database-url", required=True)
    p.add_argument("--out", default="data/backup_restore_certification.json")
    args = p.parse_args()
    report = certify(args.database_url)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
