from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.core.database import normalize_database_url
from app.repositories import RepositoryContainer
from scripts.export_sqlite_snapshot import export_snapshot
from scripts.import_snapshot_to_postgres import import_snapshot
from scripts.verify_migration import verify


def _create_temp_database(database_url: str) -> tuple[str, str]:
    url = make_url(normalize_database_url(database_url, ""))
    temp_name = f"careeros_mig_{uuid4().hex[:10]}"
    admin_db = "postgres" if url.database != "postgres" else url.database
    admin_url = url.set(database=admin_db)
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    with engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{temp_name}"'))
    engine.dispose()
    return temp_name, url.set(database=temp_name).render_as_string(hide_password=False)


def _drop_temp_database(database_url: str, temp_name: str) -> None:
    url = make_url(normalize_database_url(database_url, ""))
    admin_db = "postgres" if url.database != "postgres" else url.database
    engine = create_engine(url.set(database=admin_db), isolation_level="AUTOCOMMIT", future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=:name AND pid <> pg_backend_pid()"), {"name": temp_name})
            conn.execute(text(f'DROP DATABASE IF EXISTS "{temp_name}"'))
    finally:
        engine.dispose()


def _seed_fixture(db_path: Path) -> dict:
    embedding = EmbeddingGateway(EmbeddingConfig(provider="local_hash", model="local-hash-v1", dimensions=64))
    repos = RepositoryContainer.build_sqlite(
        db_path=str(db_path), database_url="", app_secret_key="migration-certification-secret-" + "x" * 32,
        session_ttl_hours=24, embedding_gateway=embedding, app_env="development",
    )
    tenant = "migration-cert-org"
    repos.identity.ensure_tenant(tenant, "Migration Certification Organization")
    user = repos.identity.ensure_user(
        email="migration-cert@invalid.local", password="Migration-Cert-Password-2026!",
        display_name="Migration Certification User", tenant_id=tenant, role="participant",
    )
    state = repos.sessions.create(tenant_id=tenant, student_user_id=user["user_id"], class_id="default", student_id=user["user_id"])
    state.profile.target_job = "Product Analyst"
    state.profile.skills = ["SQL"]
    state.profile.projects = ["Built a verified structured-data analysis project"]
    state.profile.evidence_text = "Verified project evidence: SQL analysis and documented report."
    repos.sessions.save(state)
    evidence = repos.evidence.add(state.session_id, "manual", "Verified evidence", state.profile.evidence_text, tenant_id=tenant, owner_user_id=user["user_id"])
    artifact = repos.artifacts.create_version(
        state.session_id, "career_report", "Migration Certification Artifact",
        "# Migration Certification Artifact\nEvidence-backed content.",
        tenant_id=tenant, owner_user_id=user["user_id"], created_by=user["user_id"],
        metadata={"certification": True}, evidence_links=[{"evidence_id": evidence["evidence_id"]}],
    )
    repos.workflows.ensure(state, preset_id="career_development")
    source = repos.knowledge.ingest(
        title="Migration Certification Knowledge", filename="migration.txt", mime_type="text/plain",
        text="Migration certification knowledge source with stable evidence marker.", tenant_id=tenant,
        scope="global", authority="official", effective_year="2026", priority=100,
    )
    repos.commercial.set_plan(tenant, "enterprise")
    repos.commercial.track(tenant_id=tenant, user_id=user["user_id"], session_id=state.session_id, event_name="migration_certification_fixture")
    return {"tenant_id": tenant, "user_id": user["user_id"], "session_id": state.session_id, "artifact_id": artifact["artifact_id"], "evidence_id": evidence["evidence_id"], "source_id": source["source_id"]}


def certify(database_url: str) -> dict:
    if not database_url.startswith(("postgresql://", "postgres://", "postgresql+")):
        return {"ok": False, "status": "NOT_CONFIGURED", "detail": "PostgreSQL DATABASE_URL is required"}
    temp_name = ""
    try:
        temp_name, target_url = _create_temp_database(database_url)
        with tempfile.TemporaryDirectory(prefix="careeros-migration-cert-") as td:
            root = Path(td)
            source_db = root / "source.db"
            snapshot = root / "snapshot"
            fixture = _seed_fixture(source_db)
            exported = export_snapshot(source_db, snapshot)
            env = os.environ.copy()
            env.update({"DATABASE_URL": target_url, "REPOSITORY_BACKEND": "postgresql", "APP_ENV": "staging"})
            subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True, text=True)
            imported = import_snapshot(snapshot, target_url, truncate=False, dry_run=False)
            verified = verify(snapshot, target_url)
            embedding = EmbeddingGateway(EmbeddingConfig(provider="local_hash", model="local-hash-v1", dimensions=64))
            repos = RepositoryContainer.build_postgresql(
                db_path="", database_url=target_url, app_secret_key="migration-certification-secret-" + "x" * 32,
                session_ttl_hours=24, embedding_gateway=embedding, app_env="staging",
            )
            state = repos.sessions.get(fixture["session_id"], tenant_id=fixture["tenant_id"])
            artifact = repos.artifacts.get(fixture["artifact_id"], tenant_id=fixture["tenant_id"])
            evidence = repos.evidence.list_session(fixture["session_id"], tenant_id=fixture["tenant_id"])
            key_ok = bool(state and artifact and any(x.get("evidence_id") == fixture["evidence_id"] for x in evidence))
            ok = bool(verified.get("ok")) and key_ok
            return {
                "ok": ok, "status": "PASS" if ok else "FAIL",
                "detail": "SQLite→PostgreSQL fixture migration, row-count verification and repository reads passed" if ok else "migration verification failed",
                "temp_database": temp_name, "fixture": fixture, "exported_tables": exported.get("tables", {}),
                "inserted": imported.get("inserted", {}), "verification": verified, "key_repository_reads": key_ok,
            }
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "status": "FAIL", "detail": (exc.stderr or exc.stdout or str(exc))[-3000:], "temp_database": temp_name}
    except Exception as exc:
        return {"ok": False, "status": "FAIL", "detail": str(exc), "temp_database": temp_name}
    finally:
        if temp_name:
            try:
                _drop_temp_database(database_url, temp_name)
            except Exception:
                pass


def main() -> int:
    p = argparse.ArgumentParser(description="Non-destructive SQLite→PostgreSQL migration certification using a temporary PostgreSQL database.")
    p.add_argument("--database-url", required=True)
    p.add_argument("--out", default="data/migration_certification.json")
    args = p.parse_args()
    report = certify(args.database_url)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
