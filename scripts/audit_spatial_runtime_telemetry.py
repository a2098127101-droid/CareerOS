from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.spatial_telemetry import SpatialRuntimeTelemetryService, SpatialTelemetryError


def require(path: str, *needles: str) -> None:
    content = (ROOT / path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in content]
    if missing:
        raise SystemExit(f"{path} is missing Alpha 8 runtime contract markers: {missing}")


def main() -> None:
    good = {
        "event": "frame_sample",
        "runId": "run-audit-1",
        "qualityTier": "balanced",
        "qualityRequest": "auto",
        "motionMode": "reduced",
        "fps": 47.5,
        "frameTime": {"p50": 18.1, "p95": 31.4, "p99": 43.2},
        "viewport": {"width": 1920, "height": 1080, "dpr": 1.5},
        "gpu": {
            "rendererClass": "intel",
            "webglVersion": "webgl2",
            "maxTextureSize": 16384,
            "maxTextures": 16,
            "maxSamples": 4,
            "precision": "highp",
        },
        "device": {"cores": 8, "memoryGb": 8, "webview": True},
        "reason": "sample",
        "demoMode": False,
    }
    clean = SpatialRuntimeTelemetryService.sanitize(good)
    assert clean["fps"] == 47.5
    assert clean["gpu"]["rendererClass"] == "intel"
    assert clean["motionMode"] == "reduced"

    for forbidden in ("answer", "message", "evidence", "taskMaterial", "userId", "sessionId", "renderer"):
        bad = dict(good)
        bad[forbidden] = "private learner content"
        try:
            SpatialRuntimeTelemetryService.sanitize(bad)
        except SpatialTelemetryError:
            pass
        else:
            raise SystemExit(f"telemetry accepted forbidden field: {forbidden}")

    contract = SpatialRuntimeTelemetryService.contract()
    privacy = contract["privacy"]
    assert privacy["acceptsLearnerContent"] is False
    assert privacy["storesUserId"] is False
    assert privacy["storesSessionId"] is False
    assert privacy["affectsLearningState"] is False

    require(
        "app/foundation_registration.py",
        "SpatialRuntimeTelemetryService",
        "build_spatial_runtime_router",
        "stepin_spatial_telemetry",
        "app.version = str(STEPIN_RELEASE_BASELINE",
    )
    require(
        "app/routers/spatial_telemetry.py",
        "/telemetry/contract",
        "/telemetry/summary",
        "participant account required",
    )
    require(
        "frontend/src/scene/alpha7/QualitySystem.tsx",
        "setFrameloop",
        "motionMode === 'full' ? 'always' : 'demand'",
        "frame_sample",
        "sustained_low_fps",
        "context_lost",
    )
    quality = (ROOT / "frontend/src/scene/alpha7/QualitySystem.tsx").read_text(encoding="utf-8")
    if "reducedMotion ||" in quality:
        raise SystemExit("reduced-motion is still incorrectly coupled to quality downgrade")

    client = (ROOT / "frontend/src/scene/alpha8/RuntimeTelemetry.ts").read_text(encoding="utf-8")
    if "renderer: rawRenderer" in client or "userAgent:" in client:
        raise SystemExit("client telemetry exposes a raw renderer or user-agent value")

    print({"ok": True, "contract": contract["version"], "motion": contract["motionModes"]})


if __name__ == "__main__":
    main()
