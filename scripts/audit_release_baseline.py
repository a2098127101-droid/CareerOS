from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = ROOT / "config" / "stepin_release_baseline.json"


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    locked_tests = int(baseline["locked_tests"])
    spatial_label = str(baseline["spatial_label"])
    product_version = str(baseline["product_version"])

    required_docs = {
        "README.md": [f"{locked_tests} / {locked_tests}", spatial_label],
        "README.zh-CN.md": [f"{locked_tests} / {locked_tests}", spatial_label],
        "TEST_REPORT.md": [f"{locked_tests} / {locked_tests}", spatial_label],
        "ROADMAP.md": [f"{locked_tests} / {locked_tests}", spatial_label],
        "ARCHITECTURE.md": [str(locked_tests), spatial_label],
        "deploy/PRODUCTION_CHECKLIST.md": [str(locked_tests)],
    }
    for path, needles in required_docs.items():
        content = read(path)
        missing = [needle for needle in needles if needle not in content]
        if missing:
            fail(f"{path} is out of sync with canonical baseline; missing {missing}")

    stale_tokens = (
        "204 / 204",
        "204-test",
        "204 automated tests",
        "2.2.0-beta-agent-trajectory",
    )
    for path in required_docs:
        content = read(path)
        stale = [token for token in stale_tokens if token in content]
        if stale:
            fail(f"{path} contains stale release metadata: {stale}")

    ci = read(".github/workflows/ci.yml")
    if "config/stepin_release_baseline.json" not in ci:
        fail("CI does not consume canonical release baseline")
    if re.search(r"passed_tests['\"]?\]\s*==\s*\d+", ci):
        fail("CI hard-codes locked test count instead of reading canonical baseline")

    release = read(".github/workflows/production-release-package.yml")
    if "config/stepin_release_baseline.json" not in release:
        fail("Production Release does not consume canonical release baseline")
    if f'value="v{product_version}-pr' in release:
        fail("Production Release hard-codes product version instead of reading canonical baseline")

    dockerfile = read("Dockerfile")
    docker_requirements = (
        "AS spatial-build",
        "frontend/package-lock.json",
        "npm ci",
        "npm run build",
        "COPY --from=spatial-build",
        "app/static/app",
    )
    missing_docker = [needle for needle in docker_requirements if needle not in dockerfile]
    if missing_docker:
        fail(f"Dockerfile does not enforce source-to-spatial build parity: {missing_docker}")

    runtime_metadata = read("app/release_baseline.py")
    if "config" not in runtime_metadata or "stepin_release_baseline.json" not in runtime_metadata:
        fail("runtime release metadata does not load the canonical baseline")
    registration = read("app/foundation_registration.py")
    if "app.version = str(STEPIN_RELEASE_BASELINE[\"product_version\"])" not in registration:
        fail("effective FastAPI runtime version is not derived from canonical baseline")
    if "stepin_release_baseline" not in registration:
        fail("canonical release metadata is not exposed on app.state")

    print(
        json.dumps(
            {
                "ok": True,
                "product": baseline["product"],
                "product_version": product_version,
                "spatial_label": spatial_label,
                "locked_tests": locked_tests,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
