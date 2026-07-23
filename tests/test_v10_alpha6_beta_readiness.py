from __future__ import annotations

import asyncio
from pathlib import Path

from app.auth_store import AuthStore
from app.artifact_store import ArtifactStore
from app.collaboration_store import CollaborationStore
from app.data_lifecycle import DataLifecycleService
from app.emailing import ConsoleEmailProvider, invitation_email, password_reset_email
from app.embedding_gateway import EmbeddingConfig, EmbeddingGateway
from app.evidence_graph import EvidenceGraphStore
from app.evidence_store import EvidenceStore
from app.migrations import run_migrations
from app.runtime_certification import RuntimeCertification
from app.storage import LocalStorageAdapter, StorageRegistry
from app.store import SessionStore
from app.workflow_store import WorkflowStore


def test_console_email_provider_writes_outbox_without_claiming_external_delivery(tmp_path: Path):
    outbox = tmp_path / "outbox.jsonl"
    provider = ConsoleEmailProvider(str(outbox))
    result = provider.send(to="demo@example.test", subject="Test", text="Hello")
    assert result.accepted is True
    assert result.provider == "console"
    assert "not externally delivered" in result.detail
    content = outbox.read_text(encoding="utf-8")
    assert "demo@example.test" in content
    assert '"externally_delivered": false' in content


def test_email_templates_use_generic_product_language():
    subject, body = invitation_email(product_name="CareerOS", invite_url="https://example.test/invite", role="advisor", expires_at="2030-01-01")
    assert subject == "CareerOS invitation"
    assert "advisor" in body
    reset_subject, reset_body = password_reset_email(product_name="CareerOS", reset_url="https://example.test/reset", ttl_minutes=30)
    assert reset_subject == "CareerOS password reset"
    assert "30" in reset_body


def test_runtime_certification_is_truthful_without_live_services(tmp_path: Path):
    class Settings:
        database_url = ""
        postgres_certification_file = str(tmp_path / "pg.json")
        redis_url = ""
        storage_provider = "local"
        app_env = "development"

    embedding = EmbeddingGateway(EmbeddingConfig(provider="local_hash"))
    storage = LocalStorageAdapter(str(tmp_path / "uploads"))
    cert = RuntimeCertification(settings=Settings(), embedding_gateway=embedding, object_storage=storage)
    report = asyncio.run(cert.run(storage_roundtrip=False, include_llm=False))
    by_name = {x["name"]: x for x in report["checks"]}
    assert by_name["postgresql"]["status"] == "NOT_CONFIGURED"
    assert by_name["redis"]["status"] == "NOT_CONFIGURED"
    assert by_name["semantic_embedding"]["status"] == "NOT_CONFIGURED"
    assert by_name["object_storage"]["status"] == "NOT_VERIFIED"
    assert report["all_required_pass"] is False


def test_controlled_privacy_deletion_removes_user_owned_operational_data_and_deidentifies(tmp_path: Path):
    db = tmp_path / "careeros.db"
    run_migrations(str(db))
    auth = AuthStore(str(db))
    sessions = SessionStore(str(db))
    artifacts = ArtifactStore(str(db))
    evidence = EvidenceStore(str(db))
    graph = EvidenceGraphStore(str(db))
    workflows = WorkflowStore(str(db))
    collab = CollaborationStore(str(db))
    registry = StorageRegistry(str(db))
    storage = LocalStorageAdapter(str(tmp_path / "uploads"))

    tenant_id = "org-delete-test"
    auth.ensure_tenant(tenant_id, "Demo Organization")
    user = auth.create_user(email="person@example.test", password="StrongPass-123!", display_name="Demo User", tenant_id=tenant_id, role="participant")
    state = sessions.create(tenant_id=tenant_id, student_user_id=user["user_id"], class_id="default")
    evidence.add(state.session_id, "upload", "Evidence", "A user-owned fact", tenant_id=tenant_id, owner_user_id=user["user_id"])
    artifacts.create_version(state.session_id, "report", "Report", "Sensitive user-owned content", tenant_id=tenant_id, owner_user_id=user["user_id"])
    workflows.ensure(state)
    collab.add_feedback(state.session_id, "Advisor note", tenant_id=tenant_id)
    collab.create_task("Task", "followup", session_id=state.session_id, tenant_id=tenant_id, owner_user_id=user["user_id"])
    stored = storage.put(tenant_id=tenant_id, owner_id=user["user_id"], filename="private.txt", content=b"private", content_type="text/plain")
    registry.record(stored=stored, tenant_id=tenant_id, owner_user_id=user["user_id"], session_id=state.session_id)

    service = DataLifecycleService(
        sessions=sessions, artifacts=artifacts, evidence=evidence, evidence_graph=graph,
        workflows=workflows, collaboration=collab, identity=auth,
        storage_registry=registry, object_storage=storage,
    )
    plan = service.plan_user_deletion(tenant_id=tenant_id, user_id=user["user_id"])
    assert plan.session_ids == [state.session_id]
    assert plan.artifacts >= 1 and plan.evidence_items >= 1 and plan.files == 1

    result = service.execute_user_deletion(tenant_id=tenant_id, user_id=user["user_id"])
    assert result["deleted"]["sessions"] == 1
    assert result["deleted"]["files"] == 1
    assert sessions.list(tenant_id=tenant_id, student_user_id=user["user_id"]) == []
    archived = auth.get_user(user["user_id"], include_memberships=True)
    assert archived["status"] == "archived"
    assert archived["display_name"] == "Deleted User"
    assert archived["email"].endswith("@invalid.local")
    assert not storage._resolve(stored.key).exists()


def test_sqlite_backup_restore_round_trip(tmp_path: Path):
    import sqlite3
    from scripts.backup_database import backup_sqlite
    from scripts.restore_database import restore_sqlite, verify_manifest
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as conn:
        conn.execute("CREATE TABLE sample(id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO sample(value) VALUES('alpha')")
        conn.commit()
    backup = tmp_path / "backup.db"
    result = backup_sqlite(source, backup)
    manifest = {"backend": "sqlite", **result}
    manifest_path = backup.with_suffix(backup.suffix + ".manifest.json")
    import json
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_manifest(backup)["sha256"] == result["sha256"]
    target = tmp_path / "restored.db"
    restore_sqlite(backup, target)
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT value FROM sample").fetchone()[0] == "alpha"


def test_sqlalchemy_identity_anonymization_parity(tmp_path: Path):
    from sqlalchemy import create_engine
    from app.core.database import BASELINE_METADATA
    from app.repositories.container import RepositoryContainer
    engine = create_engine(f"sqlite:///{(tmp_path/'parity.db').as_posix()}", future=True)
    BASELINE_METADATA.create_all(engine)
    repos = RepositoryContainer.build_sqlalchemy_core_for_testing(
        engine=engine,
        db_path=str(tmp_path/'parity.db'),
        app_secret_key='x'*40,
        session_ttl_hours=168,
        embedding_gateway=EmbeddingGateway(EmbeddingConfig()),
    )
    identity = repos['identity']
    identity.ensure_tenant('org-a6','Org A6')
    user = identity.create_user(email='delete@org.test', password='Password-12345', display_name='Delete User', tenant_id='org-a6', role='participant')
    result = identity.anonymize_user_identity(user_id=user['user_id'], tenant_id='org-a6')
    assert result['status']=='archived'
    archived = identity.get_user(user['user_id'], include_memberships=True)
    assert archived['status']=='archived' and archived['email'].endswith('@invalid.local')
