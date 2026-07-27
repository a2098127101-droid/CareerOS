from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable
import threading

Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]

_SCHEMA_READY: set[str] = set()
_SCHEMA_LOCK = threading.RLock()


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    except sqlite3.DatabaseError:
        return set()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _add_column(conn: sqlite3.Connection, table: str, definition: str) -> None:
    if not _table_exists(conn, table):
        return
    name = definition.split()[0]
    if name not in _columns(conn, table):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def _migration_1_identity_and_tenant(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            branding_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS tenant_memberships (
            membership_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id, user_id, role),
            FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS classes (
            class_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id, name),
            FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id)
        );

        CREATE TABLE IF NOT EXISTS class_memberships (
            class_membership_id TEXT PRIMARY KEY,
            class_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(class_id, user_id, role),
            FOREIGN KEY(class_id) REFERENCES classes(class_id),
            FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS auth_sessions (
            auth_session_id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            role TEXT NOT NULL,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            revoked_at DATETIME,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id)
        );

        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            reset_id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL,
            expires_at DATETIME NOT NULL,
            used_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_memberships_user ON tenant_memberships(user_id, tenant_id);
        CREATE INDEX IF NOT EXISTS idx_class_memberships_user ON class_memberships(user_id, tenant_id);
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token_hash);
        """
    )

    _add_column(conn, "sessions", "tenant_id TEXT NOT NULL DEFAULT 'demo-school'")
    _add_column(conn, "sessions", "student_user_id TEXT NOT NULL DEFAULT ''")
    _add_column(conn, "sessions", "class_id TEXT NOT NULL DEFAULT 'default'")
    _add_column(conn, "sessions", "created_at DATETIME")

    for table, definition in [
        ("artifacts", "tenant_id TEXT NOT NULL DEFAULT 'demo-school'"),
        ("artifacts", "owner_user_id TEXT NOT NULL DEFAULT ''"),
        ("evidence_items", "tenant_id TEXT NOT NULL DEFAULT 'demo-school'"),
        ("evidence_items", "owner_user_id TEXT NOT NULL DEFAULT ''"),
        ("teacher_feedback", "tenant_id TEXT NOT NULL DEFAULT 'demo-school'"),
        ("teacher_feedback", "teacher_user_id TEXT NOT NULL DEFAULT ''"),
        ("ai_tasks", "owner_user_id TEXT NOT NULL DEFAULT ''"),
        ("knowledge_sources", "tenant_id TEXT NOT NULL DEFAULT 'global'"),
        ("jobs", "tenant_id TEXT NOT NULL DEFAULT 'global'"),
        ("llm_usage", "tenant_id TEXT NOT NULL DEFAULT 'global'"),
    ]:
        _add_column(conn, table, definition)

    # Backfill indexed session ownership columns from the legacy JSON payload.
    if _table_exists(conn, "sessions"):
        rows = conn.execute("SELECT session_id, payload FROM sessions").fetchall()
        for session_id, payload in rows:
            try:
                data = json.loads(payload or "{}")
            except Exception:
                data = {}
            tenant_id = str(data.get("tenant_id") or "demo-school")
            class_id = str(data.get("class_id") or "default")
            student_user_id = str(data.get("student_user_id") or "")
            conn.execute(
                """UPDATE sessions SET tenant_id=?, class_id=?, student_user_id=?,
                created_at=COALESCE(created_at, updated_at, CURRENT_TIMESTAMP)
                WHERE session_id=?""",
                (tenant_id, class_id, student_user_id, session_id),
            )

        # Backfill child tenant columns from their owning session.
        for table in ("artifacts", "evidence_items", "teacher_feedback"):
            if _table_exists(conn, table) and "tenant_id" in _columns(conn, table):
                conn.execute(
                    f"""UPDATE {table}
                    SET tenant_id=COALESCE((SELECT s.tenant_id FROM sessions s WHERE s.session_id={table}.session_id), tenant_id, 'demo-school')"""
                )
        if _table_exists(conn, "ai_tasks"):
            conn.execute(
                """UPDATE ai_tasks
                SET tenant_id=COALESCE(NULLIF(tenant_id,''), (SELECT s.tenant_id FROM sessions s WHERE s.session_id=ai_tasks.session_id), 'demo-school')"""
            )

        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_tenant_updated ON sessions(tenant_id, updated_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_owner ON sessions(student_user_id, tenant_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_class ON sessions(tenant_id, class_id, updated_at DESC)")

    if _table_exists(conn, "artifacts"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_tenant_session ON artifacts(tenant_id, session_id, created_at DESC)")
    if _table_exists(conn, "evidence_items"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_tenant_session ON evidence_items(tenant_id, session_id, created_at DESC)")
    if _table_exists(conn, "teacher_feedback"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_tenant_session ON teacher_feedback(tenant_id, session_id, created_at DESC)")
    if _table_exists(conn, "knowledge_sources"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_tenant ON knowledge_sources(tenant_id, updated_at DESC)")
    if _table_exists(conn, "jobs"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id, updated_at DESC)")

    # Always provide a stable demo tenant for backwards compatibility and local showcase use.
    conn.execute(
        "INSERT OR IGNORE INTO tenants(tenant_id,name,status) VALUES('demo-school','CareerOS Demo School','active')"
    )
    conn.execute(
        "INSERT OR IGNORE INTO classes(class_id,tenant_id,name,status) VALUES('default','demo-school','默认班级','active')"
    )


def _migration_2_artifact_series(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS artifact_series (
            artifact_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            current_version_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, kind)
        );

        CREATE TABLE IF NOT EXISTS artifact_versions (
            version_id TEXT PRIMARY KEY,
            artifact_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'unknown',
            created_by TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            evidence_links_json TEXT NOT NULL DEFAULT '[]',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(artifact_id, version),
            FOREIGN KEY(artifact_id) REFERENCES artifact_series(artifact_id)
        );

        CREATE INDEX IF NOT EXISTS idx_artifact_series_session ON artifact_series(tenant_id, session_id, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_artifact_versions_series ON artifact_versions(artifact_id, version DESC);
        """
    )

    # Migrate the legacy one-row-per-version table without deleting it.
    if not _table_exists(conn, "artifacts"):
        return
    rows = conn.execute("SELECT * FROM artifacts ORDER BY created_at ASC, version ASC").fetchall()
    cols = _columns(conn, "artifacts")
    for row in rows:
        data = dict(row)
        session_id = data["session_id"]
        legacy_kind = data["kind"]
        base_kind = legacy_kind.replace("_revision", "")
        tenant_id = data.get("tenant_id") or "demo-school"
        owner_user_id = data.get("owner_user_id") or ""
        series = conn.execute(
            "SELECT artifact_id FROM artifact_series WHERE session_id=? AND kind=?", (session_id, base_kind)
        ).fetchone()
        if series:
            series_id = series[0]
        else:
            # Stable migration ID based on first legacy artifact.
            series_id = f"AS-{data['artifact_id']}"
            title = str(data.get("title") or base_kind).replace(" · 修订版", "").replace(" · 初稿", "")
            conn.execute(
                """INSERT OR IGNORE INTO artifact_series(artifact_id,tenant_id,session_id,owner_user_id,kind,title)
                VALUES(?,?,?,?,?,?)""",
                (series_id, tenant_id, session_id, owner_user_id, base_kind, title),
            )
        exists = conn.execute(
            "SELECT 1 FROM artifact_versions WHERE version_id=?", (f"VER-{data['artifact_id']}",)
        ).fetchone()
        if exists:
            continue
        maxv = conn.execute(
            "SELECT COALESCE(MAX(version),0) FROM artifact_versions WHERE artifact_id=?", (series_id,)
        ).fetchone()[0]
        source = "revision_agent" if legacy_kind.endswith("_revision") else "writer_agent"
        conn.execute(
            """INSERT INTO artifact_versions(version_id,artifact_id,tenant_id,session_id,version,content,source,metadata_json,evidence_links_json,created_at)
            VALUES(?,?,?,?,?,?,?,?,?,COALESCE(?,CURRENT_TIMESTAMP))""",
            (
                f"VER-{data['artifact_id']}", series_id, tenant_id, session_id, int(maxv) + 1,
                data.get("content") or "", source, data.get("metadata_json") or "{}",
                data.get("evidence_links_json") or "[]", data.get("created_at"),
            ),
        )
        conn.execute(
            "UPDATE artifact_series SET current_version_id=?, updated_at=COALESCE(?,CURRENT_TIMESTAMP) WHERE artifact_id=?",
            (f"VER-{data['artifact_id']}", data.get("created_at"), series_id),
        )


def _migration_3_security_audit(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS security_audit_log (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL DEFAULT 'global',
            user_id TEXT NOT NULL DEFAULT '',
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL DEFAULT '',
            resource_id TEXT NOT NULL DEFAULT '',
            success INTEGER NOT NULL DEFAULT 1,
            details_json TEXT NOT NULL DEFAULT '{}',
            ip_address TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_security_audit_tenant ON security_audit_log(tenant_id, created_at DESC);
        """
    )


def _migration_4_workflow_persistence(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflow_instances (
            workflow_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL UNIQUE,
            current_step_id TEXT NOT NULL DEFAULT 'self_exploration',
            progress INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS workflow_steps (
            workflow_step_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            step_index INTEGER NOT NULL,
            label TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'locked',
            started_at DATETIME,
            completed_at DATETIME,
            completed_by TEXT NOT NULL DEFAULT '',
            source_type TEXT NOT NULL DEFAULT '',
            source_id TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(workflow_id, step_id),
            FOREIGN KEY(workflow_id) REFERENCES workflow_instances(workflow_id)
        );

        CREATE INDEX IF NOT EXISTS idx_workflow_session ON workflow_instances(tenant_id, session_id);
        CREATE INDEX IF NOT EXISTS idx_workflow_steps_session ON workflow_steps(tenant_id, session_id, step_index);
        """
    )


def _migration_5_evidence_graph_and_traceability(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS evidence_claims (
            claim_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            claim_text TEXT NOT NULL,
            claim_type TEXT NOT NULL DEFAULT 'artifact_claim',
            status TEXT NOT NULL DEFAULT 'unverified',
            fingerprint TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS evidence_graph_edges (
            edge_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            from_type TEXT NOT NULL,
            from_id TEXT NOT NULL,
            relation TEXT NOT NULL,
            to_type TEXT NOT NULL,
            to_id TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id, from_type, from_id, relation, to_type, to_id)
        );

        CREATE TABLE IF NOT EXISTS review_records (
            review_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            artifact_id TEXT NOT NULL DEFAULT '',
            version_id TEXT NOT NULL DEFAULT '',
            total_score INTEGER,
            report_json TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_claims_session ON evidence_claims(tenant_id, session_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_graph_edges_session ON evidence_graph_edges(tenant_id, session_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_review_records_session ON review_records(tenant_id, session_id, created_at DESC);
        """
    )


def _migration_6_hybrid_retrieval_foundation(conn: sqlite3.Connection) -> None:
    # FTS5 is available on the supported SQLite build. If unavailable, the application falls back to lexical search.
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts USING fts5(chunk_id UNINDEXED, source_id UNINDEXED, content, tokenize='unicode61')"
        )
        conn.execute("DELETE FROM knowledge_chunks_fts")
        if _table_exists(conn, 'knowledge_chunks'):
            conn.execute(
                "INSERT INTO knowledge_chunks_fts(chunk_id,source_id,content) SELECT chunk_id,source_id,content FROM knowledge_chunks"
            )
    except sqlite3.DatabaseError:
        pass
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS knowledge_embeddings (
            chunk_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_version TEXT NOT NULL DEFAULT '1',
            vector_json TEXT NOT NULL,
            content_hash TEXT NOT NULL DEFAULT '',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_source ON knowledge_embeddings(source_id);
        """
    )
    _add_column(conn, 'knowledge_chunks', "content_hash TEXT NOT NULL DEFAULT ''")
    _add_column(conn, 'knowledge_chunks', "embedding_model TEXT NOT NULL DEFAULT ''")




def _migration_7_commercial_domain_profiles(conn: sqlite3.Connection) -> None:
    _add_column(conn, "tenants", "tenant_type TEXT NOT NULL DEFAULT 'organization'")
    _add_column(conn, "tenants", "product_preset TEXT NOT NULL DEFAULT 'career_development'")
    _add_column(conn, "tenants", "settings_json TEXT NOT NULL DEFAULT '{}'")
    if _table_exists(conn, "tenants"):
        conn.execute("UPDATE tenants SET name='CareerOS Demo Organization' WHERE tenant_id='demo-school' AND name='CareerOS Demo School'")
        conn.execute("UPDATE tenants SET product_preset='career_development' WHERE product_preset='' OR product_preset IS NULL")


def _migration_8_commercialization_foundation(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS plans (
            plan_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            entitlements_json TEXT NOT NULL DEFAULT '{}',
            active INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tenant_subscriptions (
            tenant_id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'active',
            billing_provider TEXT NOT NULL DEFAULT 'mock',
            external_customer_id TEXT NOT NULL DEFAULT '',
            external_subscription_id TEXT NOT NULL DEFAULT '',
            current_period_end DATETIME,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS analytics_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL DEFAULT '',
            session_id TEXT NOT NULL DEFAULT '',
            event_name TEXT NOT NULL,
            properties_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_analytics_tenant_time ON analytics_events(tenant_id,created_at DESC);
        """
    )
    defaults = {
        "free": {"ai_calls_monthly": 50, "ai_tokens_monthly": 500000, "artifact_versions": 3, "advanced_review": False, "knowledge_base": False, "team_workspace": False, "custom_models": False},
        "professional": {"ai_calls_monthly": 2000, "ai_tokens_monthly": 20000000, "artifact_versions": 100, "advanced_review": True, "knowledge_base": True, "team_workspace": False, "custom_models": True},
        "enterprise": {"ai_calls_monthly": 0, "ai_tokens_monthly": 0, "artifact_versions": 0, "advanced_review": True, "knowledge_base": True, "team_workspace": True, "custom_models": True},
    }
    for plan_id, ent in defaults.items():
        conn.execute(
            "INSERT OR IGNORE INTO plans(plan_id,name,entitlements_json) VALUES(?,?,?)",
            (plan_id, plan_id.title(), json.dumps(ent, ensure_ascii=False)),
        )
    if _table_exists(conn, "tenants"):
        for row in conn.execute("SELECT tenant_id FROM tenants").fetchall():
            conn.execute("INSERT OR IGNORE INTO tenant_subscriptions(tenant_id,plan_id,status) VALUES(?, 'free','active')", (row[0],))


def _migration_9_storage_foundation(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS stored_objects (
            object_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL DEFAULT '',
            session_id TEXT NOT NULL DEFAULT '',
            provider TEXT NOT NULL,
            object_key TEXT NOT NULL,
            filename TEXT NOT NULL,
            content_type TEXT NOT NULL DEFAULT '',
            size_bytes INTEGER NOT NULL DEFAULT 0,
            sha256 TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_stored_objects_tenant_owner ON stored_objects(tenant_id,owner_user_id,created_at DESC);
        """
    )


def _migration_10_generic_demo_tenant_cleanup(conn: sqlite3.Connection) -> None:
    """Hide the legacy demo-school seed only on fresh/unused databases.

    Existing upgraded installations with sessions or memberships keep the legacy tenant active.
    """
    if not _table_exists(conn, "tenants"):
        return
    session_count = 0
    member_count = 0
    if _table_exists(conn, "sessions"):
        try:
            session_count = int(conn.execute("SELECT COUNT(*) FROM sessions WHERE tenant_id='demo-school'").fetchone()[0] or 0)
        except sqlite3.DatabaseError:
            session_count = 0
    if _table_exists(conn, "tenant_memberships"):
        member_count = int(conn.execute("SELECT COUNT(*) FROM tenant_memberships WHERE tenant_id='demo-school'").fetchone()[0] or 0)
    if session_count == 0 and member_count == 0:
        conn.execute("UPDATE tenants SET status='legacy' WHERE tenant_id='demo-school'")
        if _table_exists(conn, "classes"):
            conn.execute("UPDATE classes SET status='legacy' WHERE tenant_id='demo-school'")


def _migration_11_semantic_rag_and_evidence_verification(conn: sqlite3.Connection) -> None:
    """Add versioned embedding metadata, RAG evaluation tables and claim verification fields."""
    _add_column(conn, "knowledge_embeddings", "provider TEXT NOT NULL DEFAULT 'local_hash'")
    _add_column(conn, "knowledge_embeddings", "dimensions INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "knowledge_embeddings", "warning TEXT NOT NULL DEFAULT ''")
    _add_column(conn, "evidence_claims", "verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED'")
    _add_column(conn, "evidence_claims", "verification_confidence REAL NOT NULL DEFAULT 0")
    _add_column(conn, "evidence_claims", "verified_by TEXT NOT NULL DEFAULT ''")
    _add_column(conn, "evidence_claims", "verified_at DATETIME")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rag_eval_cases (
            case_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'global',
            query TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'global',
            effective_year TEXT NOT NULL DEFAULT '',
            expected_source_id TEXT NOT NULL DEFAULT '',
            expected_authority TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_rag_eval_cases_tenant ON rag_eval_cases(tenant_id,active,created_at);
        CREATE TABLE IF NOT EXISTS rag_eval_runs (
            run_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'global',
            metrics_json TEXT NOT NULL DEFAULT '{}',
            cases_json TEXT NOT NULL DEFAULT '[]',
            embedding_model TEXT NOT NULL DEFAULT '',
            retrieval_mode TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_rag_eval_runs_tenant ON rag_eval_runs(tenant_id,created_at);
        """
    )



def _migration_12_runtime_infrastructure(conn: sqlite3.Connection) -> None:
    """Private object lifecycle fields used by alpha4 runtime infrastructure."""
    _add_column(conn, "stored_objects", "status TEXT NOT NULL DEFAULT 'active'")
    _add_column(conn, "stored_objects", "scan_status TEXT NOT NULL DEFAULT 'unknown'")
    _add_column(conn, "stored_objects", "deleted_at DATETIME")
    if _table_exists(conn, "stored_objects"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_stored_objects_status ON stored_objects(tenant_id,status,created_at DESC)")


def _migration_13_model_governance_identity_privacy(conn: sqlite3.Connection) -> None:
    """Model capability registry, evaluation history, invitations and privacy request foundation."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS llm_model_capabilities (
            provider_id TEXT NOT NULL,
            model TEXT NOT NULL,
            supports_streaming INTEGER NOT NULL DEFAULT 0,
            supports_json_schema INTEGER NOT NULL DEFAULT 0,
            supports_tools INTEGER NOT NULL DEFAULT 0,
            supports_vision INTEGER NOT NULL DEFAULT 0,
            supports_files INTEGER NOT NULL DEFAULT 0,
            context_window INTEGER NOT NULL DEFAULT 0,
            max_output INTEGER NOT NULL DEFAULT 0,
            reasoning_level TEXT NOT NULL DEFAULT 'none',
            latency_class TEXT NOT NULL DEFAULT 'unknown',
            input_cost_per_million REAL NOT NULL DEFAULT 0,
            output_cost_per_million REAL NOT NULL DEFAULT 0,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(provider_id, model)
        );
        CREATE INDEX IF NOT EXISTS idx_llm_model_capabilities_provider ON llm_model_capabilities(provider_id,updated_at DESC);

        CREATE TABLE IF NOT EXISTS model_eval_runs (
            eval_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'global',
            task TEXT NOT NULL DEFAULT 'evaluation',
            provider_id TEXT NOT NULL,
            model TEXT NOT NULL,
            metrics_json TEXT NOT NULL DEFAULT '{}',
            cases_json TEXT NOT NULL DEFAULT '[]',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_model_eval_runs_tenant ON model_eval_runs(tenant_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS user_invitations (
            invitation_id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            tenant_id TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            invited_by TEXT NOT NULL DEFAULT '',
            expires_at DATETIME NOT NULL,
            accepted_at DATETIME,
            revoked_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_user_invitations_tenant ON user_invitations(tenant_id,created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_user_invitations_email ON user_invitations(email,tenant_id);

        CREATE TABLE IF NOT EXISTS privacy_consents (
            consent_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            policy_version TEXT NOT NULL,
            purpose TEXT NOT NULL DEFAULT 'service',
            granted INTEGER NOT NULL DEFAULT 1,
            source TEXT NOT NULL DEFAULT 'ui',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_privacy_consents_user ON privacy_consents(tenant_id,user_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS data_subject_requests (
            request_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            request_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT NOT NULL DEFAULT '',
            result_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME
        );
        CREATE INDEX IF NOT EXISTS idx_data_subject_requests_user ON data_subject_requests(tenant_id,user_id,created_at DESC);
        """
    )


def _migration_14_billing_sandbox_foundation(conn: sqlite3.Connection) -> None:
    """Sandbox billing orders and idempotent webhook audit foundation. No real payment provider is implied."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS billing_orders (
            order_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'mock',
            external_order_id TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            amount_minor INTEGER NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'CNY',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_billing_orders_tenant ON billing_orders(tenant_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS billing_events (
            event_id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            event_key TEXT NOT NULL,
            event_type TEXT NOT NULL DEFAULT '',
            tenant_id TEXT NOT NULL DEFAULT '',
            payload_hash TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'received',
            result_json TEXT NOT NULL DEFAULT '{}',
            received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            processed_at DATETIME,
            UNIQUE(provider,event_key)
        );
        CREATE INDEX IF NOT EXISTS idx_billing_events_provider ON billing_events(provider,received_at DESC);
        CREATE INDEX IF NOT EXISTS idx_billing_events_tenant ON billing_events(tenant_id,received_at DESC);
        """
    )


def _migration_15_template_engine_foundation(conn: sqlite3.Connection) -> None:
    """Configurable workflow binding, job requirement intelligence and verification audit history."""
    _add_column(conn, "workflow_instances", "template_id TEXT NOT NULL DEFAULT 'career_development_v1'")
    if _table_exists(conn, "workflow_instances"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_template ON workflow_instances(tenant_id,template_id,updated_at DESC)")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS job_requirements (
            requirement_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'requirement',
            requirement_text TEXT NOT NULL,
            normalized_key TEXT NOT NULL DEFAULT '',
            importance INTEGER NOT NULL DEFAULT 3,
            source_type TEXT NOT NULL DEFAULT 'derived',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_job_requirements_job ON job_requirements(tenant_id,job_id,importance DESC);

        CREATE TABLE IF NOT EXISTS evidence_verification_history (
            verification_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            previous_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
            new_status TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0,
            verifier_type TEXT NOT NULL DEFAULT 'ai',
            verified_by TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_verification_history_claim ON evidence_verification_history(tenant_id,claim_id,created_at);
        CREATE INDEX IF NOT EXISTS idx_verification_history_session ON evidence_verification_history(tenant_id,session_id,created_at);
        """
    )



def _migration_16_tenant_template_registry_and_evidence_risk(conn: sqlite3.Connection) -> None:
    """Tenant-authored workflow/artifact templates plus evidence risk governance fields."""
    _add_column(conn, "evidence_claims", "risk_level TEXT NOT NULL DEFAULT 'normal'")
    _add_column(conn, "evidence_claims", "requires_human_review INTEGER NOT NULL DEFAULT 0")
    _add_column(conn, "evidence_verification_history", "risk_level TEXT NOT NULL DEFAULT 'normal'")
    _add_column(conn, "evidence_verification_history", "requires_human_review INTEGER NOT NULL DEFAULT 0")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workflow_template_definitions (
            template_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            preset_id TEXT NOT NULL,
            name TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft',
            definition_json TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_workflow_template_defs_tenant ON workflow_template_definitions(tenant_id,preset_id,status,version DESC);

        CREATE TABLE IF NOT EXISTS artifact_template_definitions (
            template_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            label TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft',
            aliases_json TEXT NOT NULL DEFAULT '[]',
            schema_json TEXT NOT NULL DEFAULT '{}',
            renderer TEXT NOT NULL DEFAULT 'structured_text',
            review_rubric TEXT NOT NULL DEFAULT 'general_v1',
            presets_json TEXT NOT NULL DEFAULT '[]',
            created_by TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_artifact_template_defs_tenant ON artifact_template_definitions(tenant_id,kind,status,version DESC);
        """
    )


def _migration_17_unified_runtime_entities(conn: sqlite3.Connection) -> None:
    """Unified H5 runtime persistence for API-authoritative workspace entities."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS unified_runtime_entities (
            tenant_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL DEFAULT '',
            payload_json TEXT NOT NULL DEFAULT '{}',
            deleted_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(tenant_id, entity_type, entity_id)
        );
        CREATE INDEX IF NOT EXISTS idx_unified_runtime_tenant_type_updated
            ON unified_runtime_entities(tenant_id, entity_type, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_unified_runtime_owner
            ON unified_runtime_entities(tenant_id, owner_user_id, entity_type);
        """
    )


def _migration_18_unified_runtime_consistency(conn: sqlite3.Connection) -> None:
    """v1.4 runtime isolation, optimistic concurrency, and delta-sync metadata.

    Rebuild the v1.3 compatibility table so private entity IDs are unique per owner rather than
    tenant-wide. Existing rows are preserved. A tenant revision clock allows lossless delta sync
    without full-collection replacement.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(unified_runtime_entities)").fetchall()}
    pk_cols = [row[1] for row in sorted(conn.execute("PRAGMA table_info(unified_runtime_entities)").fetchall(), key=lambda r: r[5]) if row[5]]
    needs_rebuild = (
        "version" not in cols or "revision" not in cols or "updated_by" not in cols
        or pk_cols != ["tenant_id", "owner_user_id", "entity_type", "entity_id"]
    )
    if needs_rebuild:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS unified_runtime_entities_v14 (
                tenant_id TEXT NOT NULL,
                owner_user_id TEXT NOT NULL DEFAULT '',
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                version INTEGER NOT NULL DEFAULT 1,
                revision INTEGER NOT NULL DEFAULT 0,
                updated_by TEXT NOT NULL DEFAULT '',
                deleted_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(tenant_id, owner_user_id, entity_type, entity_id)
            );
            """
        )
        legacy_cols = cols
        version_expr = "COALESCE(version,1)" if "version" in legacy_cols else "1"
        revision_expr = "COALESCE(revision,0)" if "revision" in legacy_cols else "0"
        updated_by_expr = "COALESCE(updated_by,'')" if "updated_by" in legacy_cols else "''"
        conn.execute(
            f"""INSERT OR REPLACE INTO unified_runtime_entities_v14
            (tenant_id,owner_user_id,entity_type,entity_id,payload_json,version,revision,updated_by,deleted_at,created_at,updated_at)
            SELECT tenant_id,COALESCE(owner_user_id,''),entity_type,entity_id,payload_json,
                   {version_expr},{revision_expr},{updated_by_expr},deleted_at,created_at,updated_at
            FROM unified_runtime_entities"""
        )
        conn.executescript(
            """
            DROP TABLE unified_runtime_entities;
            ALTER TABLE unified_runtime_entities_v14 RENAME TO unified_runtime_entities;
            """
        )
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS unified_runtime_revisions (
            tenant_id TEXT PRIMARY KEY,
            revision INTEGER NOT NULL DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_unified_runtime_tenant_type_revision
            ON unified_runtime_entities(tenant_id, entity_type, revision);
        CREATE INDEX IF NOT EXISTS idx_unified_runtime_owner
            ON unified_runtime_entities(tenant_id, owner_user_id, entity_type, revision);
        """
    )
    tenants = conn.execute("SELECT DISTINCT tenant_id FROM unified_runtime_entities").fetchall()
    for row in tenants:
        tenant = row[0]
        current = conn.execute(
            "SELECT COALESCE(MAX(revision),0) FROM unified_runtime_entities WHERE tenant_id=?", (tenant,)
        ).fetchone()[0]
        conn.execute(
            "INSERT OR IGNORE INTO unified_runtime_revisions(tenant_id,revision) VALUES(?,?)",
            (tenant, int(current or 0)),
        )

    # Canonical-domain lifecycle metadata required by the v1.4 workspace API.
    _add_column(conn, "evidence_items", "metadata_json TEXT NOT NULL DEFAULT '{}'")
    _add_column(conn, "evidence_items", "version INTEGER NOT NULL DEFAULT 1")
    _add_column(conn, "evidence_items", "updated_at DATETIME")
    _add_column(conn, "evidence_items", "deleted_at DATETIME")
    _add_column(conn, "artifact_series", "version INTEGER NOT NULL DEFAULT 1")
    _add_column(conn, "artifact_series", "deleted_at DATETIME")
    _add_column(conn, "ai_tasks", "version INTEGER NOT NULL DEFAULT 1")
    _add_column(conn, "ai_tasks", "completed_at DATETIME")
    if _table_exists(conn, "evidence_items"):
        conn.execute("UPDATE evidence_items SET updated_at=COALESCE(updated_at,created_at,CURRENT_TIMESTAMP)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_owner_active ON evidence_items(tenant_id,owner_user_id,deleted_at,updated_at DESC)")
    if _table_exists(conn, "artifact_series"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifact_owner_active ON artifact_series(tenant_id,owner_user_id,deleted_at,updated_at DESC)")
    if _table_exists(conn, "ai_tasks"):
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_owner_active ON ai_tasks(tenant_id,owner_user_id,status,updated_at DESC)")



def _migration_19_artifact_workspace_multi_series(conn: sqlite3.Connection) -> None:
    """Allow multiple workspace artifacts of the same kind in one session.

    v1.0-v1.3 enforced UNIQUE(session_id, kind), which was correct for legacy writer-agent
    streams but wrong for a workspace where a user may maintain multiple resumes/reports.
    Rebuild only when the legacy unique constraint is still present.
    """
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='artifact_series'").fetchone()
    ddl = (row[0] if row else "") or ""
    compact = ddl.replace(" ", "").replace("\n", "").lower()
    if "unique(session_id,kind)" not in compact:
        return
    conn.executescript("""
        CREATE TABLE artifact_series_v14 (
            artifact_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL DEFAULT '',
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            current_version_id TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            deleted_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO artifact_series_v14
        (artifact_id,tenant_id,session_id,owner_user_id,kind,title,current_version_id,version,deleted_at,created_at,updated_at)
        SELECT artifact_id,tenant_id,session_id,COALESCE(owner_user_id,''),kind,title,current_version_id,
               COALESCE(version,1),deleted_at,created_at,updated_at
        FROM artifact_series;
        DROP TABLE artifact_series;
        ALTER TABLE artifact_series_v14 RENAME TO artifact_series;
        CREATE INDEX IF NOT EXISTS idx_artifact_series_session ON artifact_series(tenant_id,session_id,updated_at);
        CREATE INDEX IF NOT EXISTS idx_artifact_owner_active ON artifact_series(tenant_id,owner_user_id,deleted_at,updated_at DESC);
    """)



def _migration_20_security_trust_and_domain_intelligence(conn: sqlite3.Connection) -> None:
    """CareerOS v1.5 first-class Claim → Capability → Requirement → Gap domain.

    Also upgrades Evidence from a client-controlled boolean to a server-owned trust lifecycle.
    """
    # Evidence trust lifecycle.
    _add_column(conn, "evidence_items", "verification_status TEXT NOT NULL DEFAULT 'SELF_REPORTED'")
    _add_column(conn, "evidence_items", "verification_method TEXT NOT NULL DEFAULT ''")
    _add_column(conn, "evidence_items", "verification_confidence REAL NOT NULL DEFAULT 0")
    _add_column(conn, "evidence_items", "verified_by TEXT NOT NULL DEFAULT ''")
    _add_column(conn, "evidence_items", "verified_at DATETIME")
    _add_column(conn, "evidence_items", "source_hash TEXT NOT NULL DEFAULT ''")
    if _table_exists(conn, "evidence_items"):
        conn.execute("""UPDATE evidence_items
            SET verification_status=CASE WHEN COALESCE(verified,0)=1 THEN 'VERIFIED' ELSE 'SELF_REPORTED' END
            WHERE verification_status IS NULL OR verification_status='' OR verification_status='SELF_REPORTED'""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evidence_verification ON evidence_items(tenant_id,owner_user_id,verification_status,updated_at DESC)")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS evidence_item_verification_history (
            history_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            previous_status TEXT NOT NULL,
            new_status TEXT NOT NULL,
            decision TEXT NOT NULL DEFAULT '',
            confidence REAL NOT NULL DEFAULT 0,
            method TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL DEFAULT '',
            actor_user_id TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_evidence_item_verification_history
          ON evidence_item_verification_history(tenant_id,evidence_id,created_at DESC);

        CREATE TABLE IF NOT EXISTS capability_taxonomies (
            taxonomy_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            created_by TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id,name)
        );

        CREATE TABLE IF NOT EXISTS capabilities (
            capability_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            taxonomy_id TEXT NOT NULL,
            capability_key TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            description TEXT NOT NULL DEFAULT '',
            aliases_json TEXT NOT NULL DEFAULT '[]',
            level_scale_json TEXT NOT NULL DEFAULT '{}',
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            created_by TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id,taxonomy_id,capability_key)
        );
        CREATE INDEX IF NOT EXISTS idx_capabilities_tenant_category ON capabilities(tenant_id,category,status,name);

        CREATE TABLE IF NOT EXISTS capability_versions (
            capability_version_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            capability_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL,
            changed_by TEXT NOT NULL DEFAULT '',
            change_reason TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(capability_id,version)
        );

        CREATE TABLE IF NOT EXISTS domain_claims (
            claim_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_locator TEXT NOT NULL DEFAULT '',
            claim_text TEXT NOT NULL,
            normalized_text TEXT NOT NULL DEFAULT '',
            claim_type TEXT NOT NULL DEFAULT 'experience',
            status TEXT NOT NULL DEFAULT 'active',
            version INTEGER NOT NULL DEFAULT 1,
            supersedes_claim_id TEXT NOT NULL DEFAULT '',
            created_by TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            deleted_at DATETIME,
            UNIQUE(tenant_id,session_id,source_type,source_id,source_locator)
        );
        CREATE INDEX IF NOT EXISTS idx_domain_claims_session ON domain_claims(tenant_id,session_id,owner_user_id,status,updated_at DESC);

        CREATE TABLE IF NOT EXISTS domain_claim_versions (
            claim_version_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL,
            changed_by TEXT NOT NULL DEFAULT '',
            change_reason TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(claim_id,version)
        );

        CREATE TABLE IF NOT EXISTS claim_evidence_links (
            link_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            evidence_id TEXT NOT NULL,
            relation TEXT NOT NULL DEFAULT 'candidate_support',
            confidence REAL NOT NULL DEFAULT 0,
            verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
            explanation TEXT NOT NULL DEFAULT '',
            verifier_type TEXT NOT NULL DEFAULT 'deterministic',
            verified_by TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id,claim_id,evidence_id,relation)
        );
        CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim ON claim_evidence_links(tenant_id,claim_id,relation,confidence DESC);
        CREATE INDEX IF NOT EXISTS idx_claim_evidence_evidence ON claim_evidence_links(tenant_id,evidence_id,relation);

        CREATE TABLE IF NOT EXISTS claim_capability_links (
            link_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            claim_id TEXT NOT NULL,
            capability_id TEXT NOT NULL,
            relation TEXT NOT NULL DEFAULT 'indicates',
            confidence REAL NOT NULL DEFAULT 0,
            explanation TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id,claim_id,capability_id,relation)
        );
        CREATE INDEX IF NOT EXISTS idx_claim_capability_capability ON claim_capability_links(tenant_id,capability_id,confidence DESC);

        CREATE TABLE IF NOT EXISTS job_requirement_versions (
            requirement_version_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            requirement_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL,
            changed_by TEXT NOT NULL DEFAULT '',
            change_reason TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(requirement_id,version)
        );
        CREATE INDEX IF NOT EXISTS idx_job_requirement_versions ON job_requirement_versions(tenant_id,job_id,requirement_id,version DESC);

        CREATE TABLE IF NOT EXISTS job_requirement_capability_links (
            link_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            requirement_id TEXT NOT NULL,
            capability_id TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 1,
            minimum_score REAL NOT NULL DEFAULT 60,
            mapping_status TEXT NOT NULL DEFAULT 'derived',
            explanation TEXT NOT NULL DEFAULT '',
            version INTEGER NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id,requirement_id,capability_id)
        );
        CREATE INDEX IF NOT EXISTS idx_requirement_capability_job ON job_requirement_capability_links(tenant_id,job_id,requirement_id);

        CREATE TABLE IF NOT EXISTS capability_assessments (
            assessment_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            capability_id TEXT NOT NULL,
            assessment_version INTEGER NOT NULL,
            potential_score REAL NOT NULL DEFAULT 0,
            verified_score REAL NOT NULL DEFAULT 0,
            confidence REAL NOT NULL DEFAULT 0,
            methodology_version TEXT NOT NULL,
            explanation_json TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(tenant_id,session_id,capability_id,assessment_version)
        );
        CREATE INDEX IF NOT EXISTS idx_capability_assessments_latest ON capability_assessments(tenant_id,session_id,capability_id,assessment_version DESC);

        CREATE TABLE IF NOT EXISTS capability_assessment_evidence (
            link_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            assessment_id TEXT NOT NULL,
            capability_id TEXT NOT NULL,
            claim_id TEXT NOT NULL DEFAULT '',
            evidence_id TEXT NOT NULL DEFAULT '',
            contribution_type TEXT NOT NULL,
            potential_weight REAL NOT NULL DEFAULT 0,
            verified_weight REAL NOT NULL DEFAULT 0,
            explanation TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_assessment_evidence_assessment ON capability_assessment_evidence(tenant_id,assessment_id);

        CREATE TABLE IF NOT EXISTS career_gaps (
            gap_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            requirement_id TEXT NOT NULL,
            capability_id TEXT NOT NULL DEFAULT '',
            gap_type TEXT NOT NULL,
            severity REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'open',
            version INTEGER NOT NULL DEFAULT 1,
            potential_score REAL NOT NULL DEFAULT 0,
            verified_score REAL NOT NULL DEFAULT 0,
            required_score REAL NOT NULL DEFAULT 60,
            explanation_json TEXT NOT NULL DEFAULT '{}',
            created_by TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            deleted_at DATETIME,
            UNIQUE(tenant_id,session_id,job_id,requirement_id,capability_id)
        );
        CREATE INDEX IF NOT EXISTS idx_career_gaps_session_job ON career_gaps(tenant_id,session_id,job_id,status,severity DESC);

        CREATE TABLE IF NOT EXISTS career_gap_versions (
            gap_version_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            gap_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            snapshot_json TEXT NOT NULL,
            changed_by TEXT NOT NULL DEFAULT '',
            change_reason TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(gap_id,version)
        );

        CREATE TABLE IF NOT EXISTS domain_audit_events (
            event_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            session_id TEXT NOT NULL DEFAULT '',
            actor_user_id TEXT NOT NULL DEFAULT '',
            subject_user_id TEXT NOT NULL DEFAULT '',
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            action TEXT NOT NULL,
            before_json TEXT NOT NULL DEFAULT '{}',
            after_json TEXT NOT NULL DEFAULT '{}',
            reason TEXT NOT NULL DEFAULT '',
            correlation_id TEXT NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_domain_audit_entity ON domain_audit_events(tenant_id,entity_type,entity_id,created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_domain_audit_session ON domain_audit_events(tenant_id,session_id,created_at DESC);
    """)

    _add_column(conn, "job_requirements", "version INTEGER NOT NULL DEFAULT 1")
    _add_column(conn, "job_requirements", "updated_at DATETIME")
    if _table_exists(conn, "job_requirements"):
        conn.execute("UPDATE job_requirements SET updated_at=COALESCE(updated_at,created_at,CURRENT_TIMESTAMP)")


def _migration_21_domain_intelligence_seed(conn: sqlite3.Connection) -> None:
    """Seed a stable global capability taxonomy used by deterministic v1.5 mappings."""
    taxonomy_id = "TAX-CAREEROS-CORE-V1"
    conn.execute("""INSERT OR IGNORE INTO capability_taxonomies
        (taxonomy_id,tenant_id,name,description,version,status,created_by)
        VALUES(?,?,?,?,1,'active','system')""",
        (taxonomy_id, "global", "CareerOS Core Capabilities", "Versioned baseline taxonomy for explainable career capability assessment."))
    seeds = [
        ("CAP-USER-RESEARCH","user_research","用户研究","research",["用户访谈","访谈","需求调研","user research","interview"]),
        ("CAP-REQUIREMENTS","requirements_analysis","需求分析","analysis",["需求理解","需求分析","业务需求","requirements"]),
        ("CAP-DATA-ANALYSIS","data_analysis","数据分析","analysis",["数据分析","统计分析","问卷分析","data analysis","analytics"]),
        ("CAP-SQL","sql","SQL与数据库","technical",["sql","数据库","database"]),
        ("CAP-PYTHON","python","Python","technical",["python","pandas","numpy"]),
        ("CAP-COMMUNICATION","communication","沟通表达","communication",["沟通","表达","汇报","communication","presentation"]),
        ("CAP-INSIGHT","insight_communication","洞察表达","communication",["洞察","材料总结","分析报告","insight"]),
        ("CAP-PROJECT","project_collaboration","项目协作","collaboration",["项目协作","团队协作","项目管理","project","collaboration"]),
        ("CAP-TOOLS","digital_tools","数字工具","technical",["工具能力","excel","power bi","tableau","办公软件"]),
        ("CAP-WRITING","professional_writing","专业写作","communication",["写作","报告","文案","writing"]),
    ]
    for capability_id,key,name,category,aliases in seeds:
        conn.execute("""INSERT OR IGNORE INTO capabilities
            (capability_id,tenant_id,taxonomy_id,capability_key,name,category,description,aliases_json,level_scale_json,version,status,created_by)
            VALUES(?,?,?,?,?,?,?,?,?,1,'active','system')""",
            (capability_id,"global",taxonomy_id,key,name,category,"CareerOS core capability",json.dumps(aliases,ensure_ascii=False),json.dumps({"min":0,"max":100},ensure_ascii=False)))



MIGRATIONS: list[Migration] = [
    (1, "identity_and_tenant_foundation", _migration_1_identity_and_tenant),
    (2, "artifact_series_v2", _migration_2_artifact_series),
    (3, "security_audit_foundation", _migration_3_security_audit),
    (4, "workflow_persistence", _migration_4_workflow_persistence),
    (5, "evidence_graph_and_traceability", _migration_5_evidence_graph_and_traceability),
    (6, "hybrid_retrieval_foundation", _migration_6_hybrid_retrieval_foundation),
    (7, "commercial_domain_profiles", _migration_7_commercial_domain_profiles),
    (8, "commercialization_foundation", _migration_8_commercialization_foundation),
    (9, "storage_foundation", _migration_9_storage_foundation),
    (10, "generic_demo_tenant_cleanup", _migration_10_generic_demo_tenant_cleanup),
    (11, "semantic_rag_and_evidence_verification", _migration_11_semantic_rag_and_evidence_verification),
    (12, "runtime_infrastructure", _migration_12_runtime_infrastructure),
    (13, "model_governance_identity_privacy", _migration_13_model_governance_identity_privacy),
    (14, "billing_sandbox_foundation", _migration_14_billing_sandbox_foundation),
    (15, "template_engine_foundation", _migration_15_template_engine_foundation),
    (16, "tenant_template_registry_and_evidence_risk", _migration_16_tenant_template_registry_and_evidence_risk),
    (17, "unified_runtime_entities", _migration_17_unified_runtime_entities),
    (18, "unified_runtime_consistency", _migration_18_unified_runtime_consistency),
    (19, "artifact_workspace_multi_series", _migration_19_artifact_workspace_multi_series),
    (20, "security_trust_and_domain_intelligence", _migration_20_security_trust_and_domain_intelligence),
    (21, "domain_intelligence_seed", _migration_21_domain_intelligence_seed),
]


def run_migrations(db_path: str) -> list[dict[str, str | int]]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    key = str(path.resolve())
    with _SCHEMA_LOCK:
        if key in _SCHEMA_READY and path.exists():
            return []

        # Canonical schema ownership: materialize every current table/index from the checked-in
        # SQLAlchemy metadata before applying forward compatibility/data migrations. Store modules no
        # longer execute CREATE TABLE statements. Alembic uses the same metadata for PostgreSQL.
        from .core.database import BASELINE_METADATA, create_database_engine
        engine = create_database_engine("", str(path))
        try:
            BASELINE_METADATA.create_all(bind=engine, checkfirst=True)
        finally:
            engine.dispose()

        applied: list[dict[str, str | int]] = []
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )"""
            )
            existing = {int(r[0]) for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
            for version, name, fn in MIGRATIONS:
                if version in existing:
                    continue
                fn(conn)
                conn.execute("INSERT INTO schema_migrations(version,name) VALUES(?,?)", (version, name))
                conn.commit()
                applied.append({"version": version, "name": name})
        _SCHEMA_READY.add(key)
        return applied


def migration_status(db_path: str) -> dict:
    path = Path(db_path)
    if not path.exists():
        return {"current": 0, "latest": MIGRATIONS[-1][0], "applied": []}
    with sqlite3.connect(path) as conn:
        try:
            rows = conn.execute("SELECT version,name,applied_at FROM schema_migrations ORDER BY version").fetchall()
        except sqlite3.DatabaseError:
            rows = []
    return {
        "current": max([int(r[0]) for r in rows], default=0),
        "latest": MIGRATIONS[-1][0],
        "applied": [{"version": int(r[0]), "name": r[1], "applied_at": r[2]} for r in rows],
    }
