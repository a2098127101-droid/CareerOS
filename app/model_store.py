from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from .models import ProviderUpsert, RouteUpsert, ModelCapabilityUpsert


@dataclass
class ProviderRecord:
    provider_id: str
    name: str
    kind: str
    base_url: str
    api_key: str
    default_model: str
    enabled: bool
    timeout_seconds: int
    extra_headers: dict[str, str]


@dataclass
class RouteRecord:
    task: str
    provider_id: str
    model: str
    fallback_provider_id: str | None
    fallback_model: str | None
    temperature: float
    max_tokens: int


class ModelConfigStore:
    def __init__(self, db_path: str, secret_key: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        digest = hashlib.sha256(secret_key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))
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

    def _encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8") if value else ""

    def _decrypt(self, value: str) -> str:
        if not value:
            return ""
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            return ""

    def upsert_provider(self, payload: ProviderUpsert) -> None:
        existing = self.get_provider(payload.provider_id)
        if payload.api_key is None and existing:
            api_key_enc = self._encrypt(existing.api_key)
        else:
            api_key_enc = self._encrypt(payload.api_key or "")
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO llm_providers(provider_id,name,kind,base_url,api_key_enc,default_model,enabled,timeout_seconds,extra_headers,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(provider_id) DO UPDATE SET
                    name=excluded.name,kind=excluded.kind,base_url=excluded.base_url,
                    api_key_enc=excluded.api_key_enc,default_model=excluded.default_model,
                    enabled=excluded.enabled,timeout_seconds=excluded.timeout_seconds,
                    extra_headers=excluded.extra_headers,updated_at=CURRENT_TIMESTAMP
                """,
                (
                    payload.provider_id,
                    payload.name,
                    payload.kind,
                    payload.base_url.rstrip("/"),
                    api_key_enc,
                    payload.default_model,
                    1 if payload.enabled else 0,
                    payload.timeout_seconds,
                    json.dumps(payload.extra_headers, ensure_ascii=False),
                ),
            )
            conn.commit()

    def get_provider(self, provider_id: str) -> ProviderRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM llm_providers WHERE provider_id=?", (provider_id,)).fetchone()
        if not row:
            return None
        return ProviderRecord(
            provider_id=row["provider_id"],
            name=row["name"],
            kind=row["kind"],
            base_url=row["base_url"],
            api_key=self._decrypt(row["api_key_enc"]),
            default_model=row["default_model"],
            enabled=bool(row["enabled"]),
            timeout_seconds=int(row["timeout_seconds"]),
            extra_headers=json.loads(row["extra_headers"] or "{}"),
        )

    def list_providers(self, reveal_secret: bool = False) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM llm_providers ORDER BY name").fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            key = self._decrypt(row["api_key_enc"])
            result.append({
                "provider_id": row["provider_id"],
                "name": row["name"],
                "kind": row["kind"],
                "base_url": row["base_url"],
                "api_key": key if reveal_secret else None,
                "has_api_key": bool(key),
                "api_key_masked": (key[:4] + "••••" + key[-4:]) if len(key) >= 10 else ("••••" if key else ""),
                "default_model": row["default_model"],
                "enabled": bool(row["enabled"]),
                "timeout_seconds": int(row["timeout_seconds"]),
                "extra_headers": json.loads(row["extra_headers"] or "{}"),
                "updated_at": row["updated_at"],
            })
        return result

    def delete_provider(self, provider_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM llm_providers WHERE provider_id=?", (provider_id,))
            conn.execute("DELETE FROM llm_routes WHERE provider_id=? OR fallback_provider_id=?", (provider_id, provider_id))
            conn.commit()

    def upsert_route(self, payload: RouteUpsert) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO llm_routes(task,provider_id,model,fallback_provider_id,fallback_model,temperature,max_tokens,updated_at)
                VALUES(?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(task) DO UPDATE SET
                    provider_id=excluded.provider_id,model=excluded.model,
                    fallback_provider_id=excluded.fallback_provider_id,fallback_model=excluded.fallback_model,
                    temperature=excluded.temperature,max_tokens=excluded.max_tokens,updated_at=CURRENT_TIMESTAMP
                """,
                (
                    payload.task,
                    payload.provider_id,
                    payload.model,
                    payload.fallback_provider_id,
                    payload.fallback_model,
                    payload.temperature,
                    payload.max_tokens,
                ),
            )
            conn.commit()

    def get_route(self, task: str) -> RouteRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM llm_routes WHERE task=?", (task,)).fetchone()
        if not row:
            return None
        return RouteRecord(
            task=row["task"],
            provider_id=row["provider_id"],
            model=row["model"],
            fallback_provider_id=row["fallback_provider_id"],
            fallback_model=row["fallback_model"],
            temperature=float(row["temperature"]),
            max_tokens=int(row["max_tokens"]),
        )

    def list_routes(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM llm_routes ORDER BY task").fetchall()
        return [dict(r) for r in rows]

    def record_usage(
        self,
        *,
        task: str,
        provider_id: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        latency_ms: int = 0,
        success: bool = True,
        error: str = "",
        tenant_id: str = "global",
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO llm_usage(tenant_id,task,provider_id,model,input_tokens,output_tokens,total_tokens,latency_ms,success,error)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (tenant_id, task, provider_id, model, input_tokens, output_tokens, total_tokens, latency_ms, 1 if success else 0, error[:2000]),
            )
            conn.commit()

    def upsert_model_capability(self, payload: ModelCapabilityUpsert) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO llm_model_capabilities(
                provider_id,model,supports_streaming,supports_json_schema,supports_tools,supports_vision,supports_files,
                context_window,max_output,reasoning_level,latency_class,input_cost_per_million,output_cost_per_million,metadata_json,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)
                ON CONFLICT(provider_id,model) DO UPDATE SET
                supports_streaming=excluded.supports_streaming,supports_json_schema=excluded.supports_json_schema,
                supports_tools=excluded.supports_tools,supports_vision=excluded.supports_vision,supports_files=excluded.supports_files,
                context_window=excluded.context_window,max_output=excluded.max_output,reasoning_level=excluded.reasoning_level,
                latency_class=excluded.latency_class,input_cost_per_million=excluded.input_cost_per_million,
                output_cost_per_million=excluded.output_cost_per_million,metadata_json=excluded.metadata_json,updated_at=CURRENT_TIMESTAMP""",
                (payload.provider_id,payload.model,int(payload.supports_streaming),int(payload.supports_json_schema),int(payload.supports_tools),
                 int(payload.supports_vision),int(payload.supports_files),payload.context_window,payload.max_output,payload.reasoning_level,
                 payload.latency_class,payload.input_cost_per_million,payload.output_cost_per_million,json.dumps(payload.metadata,ensure_ascii=False)),
            )
            conn.commit()
        return self.get_model_capability(payload.provider_id, payload.model) or {}

    def get_model_capability(self, provider_id: str, model: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM llm_model_capabilities WHERE provider_id=? AND model=?", (provider_id,model)).fetchone()
        if not row:
            return None
        data=dict(row); data['metadata']=json.loads(data.pop('metadata_json') or '{}')
        for key in ('supports_streaming','supports_json_schema','supports_tools','supports_vision','supports_files'):
            data[key]=bool(data[key])
        return data

    def list_model_capabilities(self, provider_id: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM llm_model_capabilities WHERE provider_id=? ORDER BY model", (provider_id,)).fetchall() if provider_id else conn.execute("SELECT * FROM llm_model_capabilities ORDER BY provider_id,model").fetchall()
        out=[]
        for row in rows:
            data=dict(row); data['metadata']=json.loads(data.pop('metadata_json') or '{}')
            for key in ('supports_streaming','supports_json_schema','supports_tools','supports_vision','supports_files'): data[key]=bool(data[key])
            out.append(data)
        return out

    def recommend_models(self, *, required_capabilities: list[str] | None = None, min_context_window: int = 0, max_input_cost_per_million: float | None = None, max_output_cost_per_million: float | None = None, prefer_latency: str = 'any') -> list[dict[str, Any]]:
        required=set(required_capabilities or [])
        candidates=[]
        latency_rank={'fast':0,'balanced':1,'slow':2,'unknown':3}
        for item in self.list_model_capabilities():
            provider=self.get_provider(item['provider_id'])
            if not provider or not provider.enabled: continue
            if min_context_window and int(item.get('context_window') or 0) < min_context_window: continue
            if max_input_cost_per_million is not None and float(item.get('input_cost_per_million') or 0) > max_input_cost_per_million: continue
            if max_output_cost_per_million is not None and float(item.get('output_cost_per_million') or 0) > max_output_cost_per_million: continue
            flags={
                'streaming':bool(item.get('supports_streaming')), 'json_schema':bool(item.get('supports_json_schema')),
                'tools':bool(item.get('supports_tools')), 'vision':bool(item.get('supports_vision')), 'files':bool(item.get('supports_files'))
            }
            if any(not flags.get(cap, False) for cap in required): continue
            score=100.0 - float(item.get('input_cost_per_million') or 0)*0.1 - float(item.get('output_cost_per_million') or 0)*0.1
            if prefer_latency != 'any': score -= latency_rank.get(item.get('latency_class','unknown'),3)*5
            row=dict(item); row['score']=round(score,3); candidates.append(row)
        return sorted(candidates,key=lambda x:(-x['score'],x['provider_id'],x['model']))

    def record_model_eval(self, *, eval_id: str, tenant_id: str, task: str, provider_id: str, model: str, metrics: dict, cases: list[dict]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("INSERT INTO model_eval_runs(eval_id,tenant_id,task,provider_id,model,metrics_json,cases_json) VALUES(?,?,?,?,?,?,?)",
                         (eval_id,tenant_id,task,provider_id,model,json.dumps(metrics,ensure_ascii=False),json.dumps(cases,ensure_ascii=False)))
            conn.commit()

    def list_model_evals(self, tenant_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows=conn.execute("SELECT * FROM model_eval_runs WHERE tenant_id=? ORDER BY created_at DESC LIMIT ?",(tenant_id,limit)).fetchall()
        out=[]
        for r in rows:
            d=dict(r); d['metrics']=json.loads(d.pop('metrics_json') or '{}'); d['cases']=json.loads(d.pop('cases_json') or '[]'); out.append(d)
        return out

    def usage_summary(self, limit: int = 100, tenant_id: str | None = None) -> dict[str, Any]:
        with self._connect() as conn:
            if tenant_id is None:
                rows = conn.execute("SELECT * FROM llm_usage ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                agg = conn.execute("""SELECT COUNT(*) calls,SUM(total_tokens) tokens,AVG(latency_ms) latency,SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) errors FROM llm_usage""").fetchone()
            else:
                rows = conn.execute("SELECT * FROM llm_usage WHERE tenant_id=? ORDER BY id DESC LIMIT ?", (tenant_id,limit)).fetchall()
                agg = conn.execute("""SELECT COUNT(*) calls,SUM(total_tokens) tokens,AVG(latency_ms) latency,SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) errors FROM llm_usage WHERE tenant_id=?""", (tenant_id,)).fetchone()
        return {
            "summary": {
                "calls": int(agg["calls"] or 0),
                "tokens": int(agg["tokens"] or 0),
                "average_latency_ms": round(float(agg["latency"] or 0), 1),
                "errors": int(agg["errors"] or 0),
            },
            "recent": [dict(r) for r in rows],
        }
