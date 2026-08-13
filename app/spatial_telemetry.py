from __future__ import annotations

import math
import re
import threading
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from typing import Any


TELEMETRY_VERSION = "1.0"
EVENT_KINDS = {
    "boot",
    "frame_sample",
    "quality_change",
    "context_lost",
    "context_restored",
}
QUALITY_TIERS = {"ultra", "high", "balanced", "safe"}
QUALITY_REQUESTS = QUALITY_TIERS | {"auto"}
MOTION_MODES = {"full", "reduced", "off"}
RENDERER_CLASSES = {"nvidia", "amd", "intel", "apple", "qualcomm", "arm", "software", "other", "unknown"}
WEBGL_VERSIONS = {"webgl1", "webgl2", "unknown"}
DOWNGRADE_REASONS = {
    "boot",
    "sample",
    "manual",
    "webgl_capability",
    "sustained_low_fps",
    "context_lost",
    "context_restored",
}
_TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")


class SpatialTelemetryError(ValueError):
    pass


def _number(value: Any, *, minimum: float, maximum: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpatialTelemetryError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise SpatialTelemetryError(f"{name} is outside the allowed range")
    return round(value, 3)


def _integer(value: Any, *, minimum: int, maximum: int, name: str) -> int:
    number = _number(value, minimum=minimum, maximum=maximum, name=name)
    if not float(number).is_integer():
        raise SpatialTelemetryError(f"{name} must be an integer")
    return int(number)


def _enum(value: Any, allowed: set[str], *, name: str, default: str = "") -> str:
    if value is None and default:
        return default
    token = str(value or "").strip().lower()
    if token not in allowed:
        raise SpatialTelemetryError(f"{name} is not allowed")
    return token


def _token(value: Any, *, name: str) -> str:
    token = str(value or "").strip()
    if not _TOKEN.fullmatch(token):
        raise SpatialTelemetryError(f"{name} is invalid")
    return token


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))
    return round(float(ordered[position]), 2)


class SpatialRuntimeTelemetryService:
    """Store render-only certification telemetry without learner content or identity.

    The persistent analytics event deliberately uses blank user/session identifiers. The
    process-local bounded buffer exists only to provide an immediate tenant-scoped
    certification summary and never becomes part of SceneState, Evidence, Artifact,
    Capability, Learner Trajectory, or Agent state.
    """

    MAX_RECENT_PER_TENANT = 2048

    def __init__(self, commercial_store: Any | None = None):
        self.commercial_store = commercial_store
        self._lock = threading.Lock()
        self._recent: dict[str, deque[dict[str, Any]]] = defaultdict(
            lambda: deque(maxlen=self.MAX_RECENT_PER_TENANT)
        )

    @staticmethod
    def contract() -> dict[str, Any]:
        return {
            "ok": True,
            "version": TELEMETRY_VERSION,
            "events": sorted(EVENT_KINDS),
            "qualityTiers": sorted(QUALITY_TIERS),
            "motionModes": sorted(MOTION_MODES),
            "privacy": {
                "acceptsLearnerContent": False,
                "acceptsEvidenceText": False,
                "acceptsTaskMaterial": False,
                "storesUserId": False,
                "storesSessionId": False,
                "storesRawUserAgent": False,
                "storesRawRenderer": False,
                "affectsLearningState": False,
            },
        }

    @staticmethod
    def sanitize(payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SpatialTelemetryError("payload must be an object")
        allowed_top = {
            "event", "runId", "qualityTier", "qualityRequest", "motionMode",
            "fps", "frameTime", "viewport", "gpu", "device", "reason", "demoMode",
        }
        unknown = set(payload) - allowed_top
        if unknown:
            raise SpatialTelemetryError(f"unknown telemetry fields: {sorted(unknown)}")

        event = _enum(payload.get("event"), EVENT_KINDS, name="event")
        result: dict[str, Any] = {
            "event": event,
            "runId": _token(payload.get("runId"), name="runId"),
            "qualityTier": _enum(payload.get("qualityTier"), QUALITY_TIERS, name="qualityTier"),
            "qualityRequest": _enum(payload.get("qualityRequest"), QUALITY_REQUESTS, name="qualityRequest"),
            "motionMode": _enum(payload.get("motionMode"), MOTION_MODES, name="motionMode"),
            "demoMode": bool(payload.get("demoMode", False)),
        }
        if "reason" in payload:
            result["reason"] = _enum(payload.get("reason"), DOWNGRADE_REASONS, name="reason")
        if "fps" in payload:
            result["fps"] = _number(payload["fps"], minimum=0, maximum=300, name="fps")

        frame_time = payload.get("frameTime")
        if frame_time is not None:
            if not isinstance(frame_time, dict) or set(frame_time) - {"p50", "p95", "p99"}:
                raise SpatialTelemetryError("frameTime contains unsupported fields")
            result["frameTime"] = {
                key: _number(frame_time[key], minimum=0, maximum=1000, name=f"frameTime.{key}")
                for key in ("p50", "p95", "p99") if key in frame_time
            }

        viewport = payload.get("viewport")
        if viewport is not None:
            if not isinstance(viewport, dict) or set(viewport) - {"width", "height", "dpr"}:
                raise SpatialTelemetryError("viewport contains unsupported fields")
            result["viewport"] = {
                "width": _integer(viewport.get("width"), minimum=160, maximum=16384, name="viewport.width"),
                "height": _integer(viewport.get("height"), minimum=160, maximum=16384, name="viewport.height"),
                "dpr": _number(viewport.get("dpr"), minimum=0.5, maximum=4, name="viewport.dpr"),
            }

        gpu = payload.get("gpu")
        if gpu is not None:
            if not isinstance(gpu, dict) or set(gpu) - {"rendererClass", "webglVersion", "maxTextureSize", "maxTextures", "maxSamples", "precision"}:
                raise SpatialTelemetryError("gpu contains unsupported fields")
            precision = str(gpu.get("precision") or "unknown").strip().lower()
            if precision not in {"highp", "mediump", "lowp", "unknown"}:
                raise SpatialTelemetryError("gpu.precision is not allowed")
            result["gpu"] = {
                "rendererClass": _enum(gpu.get("rendererClass"), RENDERER_CLASSES, name="gpu.rendererClass", default="unknown"),
                "webglVersion": _enum(gpu.get("webglVersion"), WEBGL_VERSIONS, name="gpu.webglVersion", default="unknown"),
                "maxTextureSize": _integer(gpu.get("maxTextureSize", 0), minimum=0, maximum=65536, name="gpu.maxTextureSize"),
                "maxTextures": _integer(gpu.get("maxTextures", 0), minimum=0, maximum=256, name="gpu.maxTextures"),
                "maxSamples": _integer(gpu.get("maxSamples", 0), minimum=0, maximum=64, name="gpu.maxSamples"),
                "precision": precision,
            }

        device = payload.get("device")
        if device is not None:
            if not isinstance(device, dict) or set(device) - {"cores", "memoryGb", "webview"}:
                raise SpatialTelemetryError("device contains unsupported fields")
            result["device"] = {
                "cores": _integer(device.get("cores", 0), minimum=0, maximum=64, name="device.cores"),
                "memoryGb": _number(device.get("memoryGb", 0), minimum=0, maximum=128, name="device.memoryGb"),
                "webview": bool(device.get("webview", False)),
            }
        return result

    def ingest(self, *, tenant_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        clean = self.sanitize(payload)
        observed_at = datetime.now(timezone.utc).isoformat()
        row = {**clean, "observedAt": observed_at}
        with self._lock:
            self._recent[tenant_id].append(row)
        if self.commercial_store is not None:
            self.commercial_store.track(
                tenant_id=tenant_id,
                user_id="",
                session_id="",
                event_name=f"spatial_runtime_{clean['event']}",
                properties=clean,
            )
        return {"ok": True, "accepted": True, "version": TELEMETRY_VERSION}

    def summary(self, *, tenant_id: str) -> dict[str, Any]:
        with self._lock:
            rows = list(self._recent.get(tenant_id) or [])
        events = Counter(str(row.get("event") or "") for row in rows)
        tiers = Counter(str(row.get("qualityTier") or "") for row in rows)
        motion = Counter(str(row.get("motionMode") or "") for row in rows)
        reasons = Counter(str(row.get("reason") or "") for row in rows if row.get("reason"))
        fps_values = [float(row["fps"]) for row in rows if isinstance(row.get("fps"), (int, float))]
        frame_p95 = [float((row.get("frameTime") or {}).get("p95")) for row in rows if isinstance((row.get("frameTime") or {}).get("p95"), (int, float))]
        return {
            "ok": True,
            "version": TELEMETRY_VERSION,
            "scope": "tenant_process_window",
            "samples": len(rows),
            "runs": len({row.get("runId") for row in rows if row.get("runId")}),
            "events": dict(events),
            "qualityTiers": dict(tiers),
            "motionModes": dict(motion),
            "reasons": dict(reasons),
            "performance": {
                "fpsAverage": round(sum(fps_values) / len(fps_values), 2) if fps_values else 0.0,
                "fpsP10": _percentile(fps_values, .10),
                "fpsP50": _percentile(fps_values, .50),
                "frameTimeP95AverageMs": round(sum(frame_p95) / len(frame_p95), 2) if frame_p95 else 0.0,
            },
            "privacy": self.contract()["privacy"],
        }
