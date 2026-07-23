from __future__ import annotations

import json
import sqlite3
import threading
import hashlib
from uuid import uuid4
from pathlib import Path
from typing import Any


DEFAULT_ENTITLEMENTS: dict[str, dict[str, Any]] = {
    "free": {
        "ai_calls_monthly": 50,
        "ai_tokens_monthly": 500_000,
        "artifact_versions": 3,
        "advanced_review": False,
        "knowledge_base": False,
        "team_workspace": False,
        "custom_models": False,
    },
    "professional": {
        "ai_calls_monthly": 2_000,
        "ai_tokens_monthly": 20_000_000,
        "artifact_versions": 100,
        "advanced_review": True,
        "knowledge_base": True,
        "team_workspace": False,
        "custom_models": True,
    },
    "enterprise": {
        "ai_calls_monthly": 0,
        "ai_tokens_monthly": 0,
        "artifact_versions": 0,
        "advanced_review": True,
        "knowledge_base": True,
        "team_workspace": True,
        "custom_models": True,
    },
}


class CommercialStore:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Ensure the canonical SQLite compatibility schema via the centralized migration layer.

        Store modules no longer own CREATE TABLE/CREATE INDEX DDL. The checked-in schema manifest
        and versioned migrations are the single compatibility source used by both local SQLite and
        Alembic/PostgreSQL provisioning.
        """
        from .migrations import run_migrations
        run_migrations(str(self.db_path))

    def ensure_subscription(self, tenant_id: str, plan_id: str = "free") -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO tenant_subscriptions(tenant_id,plan_id,status) VALUES(?,?, 'active')",
                (tenant_id, plan_id),
            )
            conn.commit()

    def set_plan(self, tenant_id: str, plan_id: str) -> None:
        if plan_id not in DEFAULT_ENTITLEMENTS:
            with self._connect() as conn:
                exists = conn.execute("SELECT 1 FROM plans WHERE plan_id=? AND active=1", (plan_id,)).fetchone()
            if not exists:
                raise KeyError(plan_id)
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO tenant_subscriptions(tenant_id,plan_id,status,updated_at)
                VALUES(?,?, 'active',CURRENT_TIMESTAMP)
                ON CONFLICT(tenant_id) DO UPDATE SET plan_id=excluded.plan_id,status='active',updated_at=CURRENT_TIMESTAMP""",
                (tenant_id, plan_id),
            )
            conn.commit()

    def subscription(self, tenant_id: str) -> dict[str, Any]:
        self.ensure_subscription(tenant_id)
        with self._connect() as conn:
            row = conn.execute(
                """SELECT s.*,p.name plan_name,p.entitlements_json
                FROM tenant_subscriptions s JOIN plans p ON p.plan_id=s.plan_id WHERE s.tenant_id=?""",
                (tenant_id,),
            ).fetchone()
        if not row:
            return {"tenant_id": tenant_id, "plan_id": "free", "entitlements": DEFAULT_ENTITLEMENTS["free"]}
        data = dict(row)
        data["entitlements"] = json.loads(data.pop("entitlements_json") or "{}")
        return data

    def entitlement(self, tenant_id: str, feature: str, default: Any = False) -> Any:
        return self.subscription(tenant_id).get("entitlements", {}).get(feature, default)

    def list_plans(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM plans WHERE active=1 ORDER BY plan_id").fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["entitlements"] = json.loads(d.pop("entitlements_json") or "{}")
            out.append(d)
        return out

    def track(self, *, tenant_id: str, event_name: str, user_id: str = "", session_id: str = "", properties: dict | None = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO analytics_events(tenant_id,user_id,session_id,event_name,properties_json) VALUES(?,?,?,?,?)",
                (tenant_id, user_id, session_id, event_name, json.dumps(properties or {}, ensure_ascii=False)),
            )
            conn.commit()

    def analytics_summary(self, tenant_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT event_name,COUNT(*) count FROM analytics_events WHERE tenant_id=? GROUP BY event_name ORDER BY count DESC",
                (tenant_id,),
            ).fetchall()
            uv = conn.execute(
                "SELECT COUNT(DISTINCT user_id) FROM analytics_events WHERE tenant_id=? AND user_id<>''",
                (tenant_id,),
            ).fetchone()[0]
        return {"events": {r["event_name"]: int(r["count"]) for r in rows}, "uv": int(uv or 0)}

    def usage_window(self, tenant_id: str) -> dict[str, int]:
        with self._connect() as conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='llm_usage'").fetchone()
            if not exists:
                return {"calls": 0, "tokens": 0}
            row = conn.execute(
                """SELECT COUNT(*) calls,COALESCE(SUM(total_tokens),0) tokens
                FROM llm_usage WHERE tenant_id=? AND created_at>=datetime('now','start of month')""",
                (tenant_id,),
            ).fetchone()
        return {"calls": int(row["calls"] or 0), "tokens": int(row["tokens"] or 0)}

    def check_ai_quota(self, tenant_id: str) -> tuple[bool, str]:
        sub = self.subscription(tenant_id)
        ent = sub.get("entitlements", {})
        usage = self.usage_window(tenant_id)
        max_calls = int(ent.get("ai_calls_monthly") or 0)
        max_tokens = int(ent.get("ai_tokens_monthly") or 0)
        if max_calls and usage["calls"] >= max_calls:
            return False, f"Monthly AI call quota reached for plan {sub.get('plan_id')}"
        if max_tokens and usage["tokens"] >= max_tokens:
            return False, f"Monthly AI token quota reached for plan {sub.get('plan_id')}"
        return True, ""


    def create_billing_order(self, *, tenant_id: str, plan_id: str, provider: str = "mock", metadata: dict | None = None) -> dict[str, Any]:
        order_id = f"ORD-{uuid4().hex[:16].upper()}"
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT INTO billing_orders(order_id,tenant_id,plan_id,provider,metadata_json) VALUES(?,?,?,?,?)",
                (order_id, tenant_id, plan_id, provider, json.dumps(metadata or {}, ensure_ascii=False)),
            )
            conn.commit()
        return self.get_billing_order(order_id, tenant_id=tenant_id)

    def get_billing_order(self, order_id: str, *, tenant_id: str = "") -> dict[str, Any]:
        with self._connect() as conn:
            if tenant_id:
                row = conn.execute("SELECT * FROM billing_orders WHERE order_id=? AND tenant_id=?", (order_id, tenant_id)).fetchone()
            else:
                row = conn.execute("SELECT * FROM billing_orders WHERE order_id=?", (order_id,)).fetchone()
        if not row:
            raise KeyError(order_id)
        data = dict(row)
        data["metadata"] = json.loads(data.pop("metadata_json") or "{}")
        return data

    def record_billing_event(self, *, provider: str, event_key: str, event_type: str, tenant_id: str, raw_payload: bytes) -> tuple[dict[str, Any], bool]:
        payload_hash = hashlib.sha256(raw_payload).hexdigest()
        with self._lock, self._connect() as conn:
            existing = conn.execute("SELECT * FROM billing_events WHERE provider=? AND event_key=?", (provider, event_key)).fetchone()
            if existing:
                data = dict(existing); data["result"] = json.loads(data.pop("result_json") or "{}")
                return data, True
            event_id = f"BEVT-{uuid4().hex[:16].upper()}"
            conn.execute(
                "INSERT INTO billing_events(event_id,provider,event_key,event_type,tenant_id,payload_hash) VALUES(?,?,?,?,?,?)",
                (event_id, provider, event_key, event_type, tenant_id, payload_hash),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM billing_events WHERE event_id=?", (event_id,)).fetchone()
        data = dict(row); data["result"] = json.loads(data.pop("result_json") or "{}")
        return data, False

    def complete_billing_event(self, *, provider: str, event_key: str, status: str, result: dict | None = None) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE billing_events SET status=?,result_json=?,processed_at=CURRENT_TIMESTAMP WHERE provider=? AND event_key=?",
                (status, json.dumps(result or {}, ensure_ascii=False), provider, event_key),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM billing_events WHERE provider=? AND event_key=?", (provider, event_key)).fetchone()
        if not row:
            raise KeyError(event_key)
        data=dict(row); data["result"] = json.loads(data.pop("result_json") or "{}")
        return data
