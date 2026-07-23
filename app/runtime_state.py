from __future__ import annotations

import importlib.util
import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol


class RuntimeStateError(RuntimeError):
    pass


class RateLimiter(Protocol):
    backend: str
    def allow(self, *, scope: str, key: str, limit: int, window_seconds: int = 60) -> bool: ...
    def capabilities(self) -> dict[str, Any]: ...


class MemoryRateLimiter:
    """Process-local sliding-window limiter for development and tests only."""
    backend = "memory"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[tuple[str, str], list[float]] = {}

    def allow(self, *, scope: str, key: str, limit: int, window_seconds: int = 60) -> bool:
        now = time.time()
        cutoff = now - max(1, int(window_seconds))
        bucket_key = (scope, key)
        with self._lock:
            bucket = [t for t in self._buckets.get(bucket_key, []) if t >= cutoff]
            if len(bucket) >= max(1, int(limit)):
                self._buckets[bucket_key] = bucket
                return False
            bucket.append(now)
            self._buckets[bucket_key] = bucket
            return True

    def capabilities(self) -> dict[str, Any]:
        return {"backend": self.backend, "distributed": False, "ready": True}


class RedisRateLimiter:
    """Atomic Redis sliding-window limiter using a sorted-set Lua script."""
    backend = "redis"
    _SCRIPT = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local cutoff = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local member = ARGV[4]
    local ttl = tonumber(ARGV[5])
    redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)
    local count = redis.call('ZCARD', key)
    if count >= limit then
      redis.call('EXPIRE', key, ttl)
      return 0
    end
    redis.call('ZADD', key, now, member)
    redis.call('EXPIRE', key, ttl)
    return 1
    """

    def __init__(self, redis_url: str, namespace: str = "careeros") -> None:
        if not importlib.util.find_spec("redis"):
            raise RuntimeStateError("redis package is required for RUNTIME_STATE_BACKEND=redis")
        import redis  # type: ignore
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.namespace = namespace
        self.client.ping()

    def allow(self, *, scope: str, key: str, limit: int, window_seconds: int = 60) -> bool:
        now_ms = int(time.time() * 1000)
        window_ms = max(1, int(window_seconds)) * 1000
        redis_key = f"{self.namespace}:rate:{scope}:{key}"
        member = f"{now_ms}:{threading.get_ident()}:{time.monotonic_ns()}"
        result = self.client.eval(
            self._SCRIPT,
            1,
            redis_key,
            now_ms,
            now_ms - window_ms,
            max(1, int(limit)),
            member,
            max(2, int(window_seconds) + 5),
        )
        return bool(int(result or 0))

    def capabilities(self) -> dict[str, Any]:
        try:
            latency_start = time.perf_counter()
            ok = bool(self.client.ping())
            latency_ms = round((time.perf_counter() - latency_start) * 1000, 2)
            return {"backend": self.backend, "distributed": True, "ready": ok, "latency_ms": latency_ms}
        except Exception as exc:
            return {"backend": self.backend, "distributed": True, "ready": False, "error": str(exc)}


def build_rate_limiter(*, backend: str, redis_url: str, namespace: str = "careeros") -> RateLimiter:
    name = (backend or "memory").strip().lower()
    if name == "redis":
        if not redis_url:
            raise RuntimeStateError("REDIS_URL is required when RUNTIME_STATE_BACKEND=redis")
        return RedisRateLimiter(redis_url, namespace=namespace)
    if name != "memory":
        raise RuntimeStateError(f"unsupported runtime state backend: {name}")
    return MemoryRateLimiter()


def redis_capabilities(redis_url: str) -> dict[str, Any]:
    if not redis_url:
        return {"configured": False, "driver_available": bool(importlib.util.find_spec("redis")), "ready": False}
    if not importlib.util.find_spec("redis"):
        return {"configured": True, "driver_available": False, "ready": False, "error": "redis package not installed"}
    try:
        import redis  # type: ignore
        client = redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
        start = time.perf_counter()
        pong = bool(client.ping())
        return {
            "configured": True,
            "driver_available": True,
            "ready": pong,
            "latency_ms": round((time.perf_counter() - start) * 1000, 2),
        }
    except Exception as exc:
        return {"configured": True, "driver_available": True, "ready": False, "error": str(exc)}
