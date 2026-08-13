from __future__ import annotations

import json
from pathlib import Path
from typing import Any


BASELINE_PATH = Path(__file__).resolve().parents[1] / "config" / "stepin_release_baseline.json"


def load_stepin_release_baseline() -> dict[str, Any]:
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    required = {
        "product", "product_version", "release_status", "spatial_runtime", "spatial_label",
        "locked_tests", "capability_verification", "target_environment_certified",
        "windows_webview2_certified",
    }
    missing = required - set(data)
    if missing:
        raise RuntimeError(f"StepIn release baseline is incomplete: {sorted(missing)}")
    return data


STEPIN_RELEASE_BASELINE = load_stepin_release_baseline()
