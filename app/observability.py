from __future__ import annotations

import importlib.util
import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "tenant_id", "user_id", "path", "method", "status_code", "latency_ms"):
            value = getattr(record, key, None)
            if value not in (None, ""):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_observability(*, json_logs: bool, sentry_dsn: str, environment: str, service_name: str) -> dict[str, Any]:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        root.addHandler(handler)
    if json_logs:
        for handler in root.handlers:
            handler.setFormatter(JsonFormatter())
    root.setLevel(logging.INFO)
    sentry_ready = False
    sentry_error = ""
    if sentry_dsn:
        if importlib.util.find_spec("sentry_sdk"):
            try:
                import sentry_sdk  # type: ignore
                sentry_sdk.init(dsn=sentry_dsn, environment=environment, traces_sample_rate=0.05)
                sentry_ready = True
            except Exception as exc:
                sentry_error = str(exc)
        else:
            sentry_error = "sentry_sdk not installed"
    return {
        "structured_logging": True,
        "json_logs": json_logs,
        "sentry_configured": bool(sentry_dsn),
        "sentry_ready": sentry_ready,
        "sentry_error": sentry_error,
        "otel_api_available": bool(importlib.util.find_spec("opentelemetry")),
        "service_name": service_name,
    }


@dataclass
class EndpointStats:
    count: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    max_latency_ms: float = 0.0


class RuntimeMetrics:
    """Low-overhead in-process metrics foundation. Production exporters can consume these counters."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stats: dict[str, EndpointStats] = defaultdict(EndpointStats)

    def observe(self, *, method: str, path: str, status_code: int, latency_ms: float) -> None:
        key = f"{method.upper()} {path}"
        with self._lock:
            item = self._stats[key]
            item.count += 1
            item.errors += int(status_code >= 500)
            item.total_latency_ms += max(0.0, latency_ms)
            item.max_latency_ms = max(item.max_latency_ms, latency_ms)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            endpoints = {}
            for key, item in self._stats.items():
                endpoints[key] = {
                    "count": item.count,
                    "errors": item.errors,
                    "avg_latency_ms": round(item.total_latency_ms / item.count, 2) if item.count else 0.0,
                    "max_latency_ms": round(item.max_latency_ms, 2),
                }
            return {"endpoints": endpoints, "endpoint_count": len(endpoints)}
