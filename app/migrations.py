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


def _migration_17_project_mvp_foundation(conn: sqlite3.Connection) -> None:
    """Add the project aggregate without changing legacy session/artifact/evidence tables."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS project_templates (
            template_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'career_planning',
            status TEXT NOT NULL DEFAULT 'draft',
            current_version_id TEXT,
            created_by TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE,
            UNIQUE(template_id, tenant_id)
        );
        CREATE INDEX IF NOT EXISTS idx_project_templates_tenant_status
            ON project_templates(tenant_id, status, updated_at);

        CREATE TABLE IF NOT EXISTS project_template_versions (
            template_version_id TEXT PRIMARY KEY,
            template_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            version INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            background TEXT NOT NULL DEFAULT '',
            objective TEXT NOT NULL DEFAULT '',
            applicable_users TEXT NOT NULL DEFAULT '',
            estimated_time_minutes INTEGER NOT NULL DEFAULT 60,
            output_type TEXT NOT NULL DEFAULT 'career_report',
            questions_json TEXT NOT NULL DEFAULT '[]',
            material_requirements_json TEXT NOT NULL DEFAULT '[]',
            artifact_structure_json TEXT NOT NULL DEFAULT '[]',
            rubric_json TEXT NOT NULL DEFAULT '{}',
            workflow_template_id TEXT NOT NULL,
            artifact_template_id TEXT NOT NULL DEFAULT 'career_report_v1',
            status TEXT NOT NULL DEFAULT 'published',
            published_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(template_id)
                REFERENCES project_templates(template_id) ON DELETE RESTRICT,
            UNIQUE(template_id, version),
            UNIQUE(template_version_id, tenant_id)
        );
        CREATE INDEX IF NOT EXISTS idx_project_template_versions_tenant_template
            ON project_template_versions(tenant_id, template_id, version);

        CREATE TABLE IF NOT EXISTS project_instances (
            project_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            template_id TEXT NOT NULL,
            template_version_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            current_step TEXT NOT NULL DEFAULT 'overview',
            current_artifact_id TEXT,
            current_artifact_version_id TEXT,
            latest_score_run_id TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            FOREIGN KEY(template_id)
                REFERENCES project_templates(template_id) ON DELETE RESTRICT,
            FOREIGN KEY(template_version_id)
                REFERENCES project_template_versions(template_version_id) ON DELETE RESTRICT,
            FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE RESTRICT,
            UNIQUE(project_id, tenant_id)
        );
        CREATE INDEX IF NOT EXISTS idx_project_instances_tenant_owner_status
            ON project_instances(tenant_id, owner_user_id, status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_project_instances_tenant_template
            ON project_instances(tenant_id, template_version_id);

        CREATE TABLE IF NOT EXISTS project_answers (
            project_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            owner_user_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            answer_json TEXT NOT NULL DEFAULT 'null',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(project_id, question_id),
            FOREIGN KEY(project_id)
                REFERENCES project_instances(project_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_project_answers_tenant_owner_project
            ON project_answers(tenant_id, owner_user_id, project_id);

        CREATE TRIGGER IF NOT EXISTS trg_project_template_versions_immutable_update
        BEFORE UPDATE ON project_template_versions
        BEGIN
            SELECT RAISE(ABORT, 'project template versions are immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_project_template_versions_immutable_delete
        BEFORE DELETE ON project_template_versions
        BEGIN
            SELECT RAISE(ABORT, 'project template versions are immutable');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_project_template_versions_tenant_guard
        BEFORE INSERT ON project_template_versions
        WHEN NOT EXISTS (
            SELECT 1 FROM project_templates
            WHERE template_id=NEW.template_id AND tenant_id=NEW.tenant_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'project template version tenant mismatch');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_project_instances_tenant_guard
        BEFORE INSERT ON project_instances
        WHEN NOT EXISTS (
            SELECT 1 FROM project_templates
            WHERE template_id=NEW.template_id AND tenant_id=NEW.tenant_id
        ) OR NOT EXISTS (
            SELECT 1 FROM project_template_versions
            WHERE template_version_id=NEW.template_version_id
              AND template_id=NEW.template_id AND tenant_id=NEW.tenant_id
        ) OR NOT EXISTS (
            SELECT 1 FROM sessions
            WHERE session_id=NEW.session_id AND tenant_id=NEW.tenant_id
              AND student_user_id=NEW.owner_user_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'project instance tenant, owner or session mismatch');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_project_instances_tenant_guard_update
        BEFORE UPDATE ON project_instances
        WHEN NOT EXISTS (
            SELECT 1 FROM project_templates
            WHERE template_id=NEW.template_id AND tenant_id=NEW.tenant_id
        ) OR NOT EXISTS (
            SELECT 1 FROM project_template_versions
            WHERE template_version_id=NEW.template_version_id
              AND template_id=NEW.template_id AND tenant_id=NEW.tenant_id
        ) OR NOT EXISTS (
            SELECT 1 FROM sessions
            WHERE session_id=NEW.session_id AND tenant_id=NEW.tenant_id
              AND student_user_id=NEW.owner_user_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'project instance tenant, owner or session mismatch');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_project_answers_owner_guard
        BEFORE INSERT ON project_answers
        WHEN NOT EXISTS (
            SELECT 1 FROM project_instances
            WHERE project_id=NEW.project_id AND tenant_id=NEW.tenant_id
              AND owner_user_id=NEW.owner_user_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'project answer tenant or owner mismatch');
        END;
        CREATE TRIGGER IF NOT EXISTS trg_project_answers_owner_guard_update
        BEFORE UPDATE ON project_answers
        WHEN NOT EXISTS (
            SELECT 1 FROM project_instances
            WHERE project_id=NEW.project_id AND tenant_id=NEW.tenant_id
              AND owner_user_id=NEW.owner_user_id
        )
        BEGIN
            SELECT RAISE(ABORT, 'project answer tenant or owner mismatch');
        END;
        """
    )


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
    (17, "project_mvp_foundation", _migration_17_project_mvp_foundation),
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
