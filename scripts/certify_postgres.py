from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
_ROOT = _BootstrapPath(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import json
import re
import secrets
from pathlib import Path

from sqlalchemy import create_engine, text

from app.core.database import BASELINE_METADATA, normalize_database_url, postgres_driver_available, schema_health
from app.core.postgres_certification import certification_record
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.models import SessionState
from app.repositories.container import RepositoryContainer
from app.storage import StoredObject
from app.pgvector_backend import pgvector_capabilities


def _safe_schema(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        raise ValueError("invalid certification schema name")
    return name


def certify(database_url: str, out_path: Path) -> dict:
    if not database_url.startswith(("postgresql://", "postgres://", "postgresql+")):
        raise ValueError("--database-url must target PostgreSQL")
    if not postgres_driver_available():
        raise RuntimeError("PostgreSQL driver missing. Install requirements-production.txt first.")

    normalized = normalize_database_url(database_url, "")
    base_engine = create_engine(normalized, future=True, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    # First verify the actual target has the expected Alembic-provisioned schema.
    target_health = schema_health(base_engine)
    if not target_health["ready"]:
        raise RuntimeError(
            "Target PostgreSQL schema is incomplete. Run `alembic upgrade head` first. "
            f"Missing: {', '.join(target_health['missing'][:12])}"
        )
    vector_caps = pgvector_capabilities(base_engine)
    if not vector_caps.get("ready"):
        raise RuntimeError("Target PostgreSQL pgvector is not ready. Run Alembic migration 0002 and ensure CREATE EXTENSION vector is permitted.")

    schema = _safe_schema(f"careeros_cert_{secrets.token_hex(6)}")
    checks: list[str] = ["target_schema_health"]
    with base_engine.connect() as conn:
        conn.exec_driver_sql(f'CREATE SCHEMA "{schema}"')

    cert_engine = create_engine(
        normalized,
        future=True,
        pool_pre_ping=True,
        connect_args={"options": f"-csearch_path={schema},public"},
    ).execution_options(schema_translate_map={None: schema})
    try:
        # Disposable schema makes the probe non-destructive while exercising PostgreSQL SQL semantics.
        BASELINE_METADATA.create_all(cert_engine)
        with cert_engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text("ALTER TABLE knowledge_embeddings ADD COLUMN IF NOT EXISTS embedding_vector vector"))
        health = schema_health(cert_engine)
        if not health["ready"]:
            raise RuntimeError(f"Certification schema incomplete: {health['missing'][:12]}")
        checks.append("sandbox_schema_create")
        if not pgvector_capabilities(cert_engine).get("ready"):
            raise RuntimeError("Certification sandbox pgvector probe failed")
        checks.append("pgvector")

        repos = RepositoryContainer.build_sqlalchemy_core_for_testing(
            engine=cert_engine,
            db_path="",
            app_secret_key="certification-secret-" + secrets.token_hex(24),
            session_ttl_hours=1,
            embedding_gateway=EmbeddingGateway(EmbeddingConfig()),
        )
        run_suffix = secrets.token_hex(4)
        tenant = f"cert-org-{run_suffix}"
        email = f"cert-user-{run_suffix}@example.invalid"
        repos["identity"].ensure_tenant(tenant, "Certification Organization")
        user = repos["identity"].create_user(
            email=email,
            password="Certification-Password-12345",
            display_name="Certification User",
            tenant_id=tenant,
            role="participant",
        )
        principal, token = repos["identity"].authenticate(
            email, "Certification-Password-12345", tenant_id=tenant
        )
        assert repos["identity"].resolve_session(token).user_id == principal.user_id
        checks.append("identity_auth")

        state = repos["sessions"].create(
            tenant_id=tenant,
            student_user_id=user["user_id"],
            class_id="default",
            student_id="cert-participant",
        )
        assert repos["sessions"].get(state.session_id, tenant_id=tenant).tenant_id == tenant
        checks.append("session_crud")

        ev = repos["evidence"].add(
            state.session_id,
            "participant_input",
            "Certification",
            "Completed a verified development activity with documented outcomes.",
            tenant_id=tenant,
            owner_user_id=user["user_id"],
        )
        art = repos["artifacts"].create_version(
            state.session_id,
            "report",
            "Certification Report",
            "Completed a verified development activity with documented outcomes.",
            tenant_id=tenant,
            owner_user_id=user["user_id"],
        )
        repos["evidence_graph"].trace_artifact_version(
            tenant_id=tenant,
            session_id=state.session_id,
            artifact_id=art["artifact_id"],
            version_id=art["version_id"],
            content=art["content"],
            evidence_items=[ev],
        )
        checks.append("artifact_evidence_trace")

        repos["workflows"].ensure(state, artifact_kinds={"report"})
        feedback = repos["collaboration"].add_feedback(
            state.session_id, "Strengthen the evidence chain.", tenant_id=tenant, teacher_name="Certification Advisor"
        )
        repos["collaboration"].ensure_task(
            "Revision", "artifact_revision", state.session_id, tenant, source="feedback", payload={"feedback_id": feedback["feedback_id"]}
        )
        checks.append("workflow_feedback_task")

        repos["knowledge"].ingest(
            title="Certification Policy",
            filename="policy.txt",
            mime_type="text/plain",
            text="Evidence-based development planning requires traceable sources.",
            tenant_id=tenant,
            scope="global",
        )
        assert repos["knowledge"].search("traceable evidence planning", tenant_id=tenant)
        repos["jobs"].upsert({"title": "Certification Role", "company": "Demo"}, tenant_id=tenant)
        checks.append("knowledge_job")

        repos["commercial"].ensure_subscription(tenant, "professional")
        repos["commercial"].track(tenant_id=tenant, user_id=user["user_id"], event_name="certification_probe")
        stored = StoredObject(
            object_id=f"OBJ-CERT-{run_suffix}", provider="local", key=f"{tenant}/{user['user_id']}/cert.txt",
            filename="cert.txt", size_bytes=1, sha256="0" * 64, content_type="text/plain",
        )
        repos["storage_registry"].record(stored=stored, tenant_id=tenant, owner_user_id=user["user_id"])
        checks.append("commercial_storage_registry")

        record = certification_record(database_url=database_url, checks=checks)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record
    finally:
        cert_engine.dispose()
        with base_engine.connect() as conn:
            conn.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        base_engine.dispose()


def main() -> int:
    p = argparse.ArgumentParser(description="Run a non-destructive live PostgreSQL repository certification probe.")
    p.add_argument("--database-url", required=True)
    p.add_argument("--out", type=Path, default=Path("data/postgres_certification.json"))
    args = p.parse_args()
    result = certify(args.database_url, args.out)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
