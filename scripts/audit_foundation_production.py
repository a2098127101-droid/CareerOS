from __future__ import annotations

import sys
from pathlib import Path

from fastapi.routing import APIRoute

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


REQUIRED = {
    ("GET", "/api/foundation/v1/me"),
    ("GET", "/api/foundation/v1/tasks/{task_id}"),
    ("PUT", "/api/foundation/v1/tasks/{task_id}/answer"),
    ("POST", "/api/foundation/v1/tasks/{task_id}/hint"),
    ("POST", "/api/foundation/v1/tasks/{task_id}/complete"),
    ("POST", "/api/foundation/v1/expression"),
    ("GET", "/api/foundation/v1/growth/{subject_user_id}"),
    ("GET", "/api/foundation/v1/cohort"),
    ("GET", "/api/foundation/v1/explorations/{kind}"),
    ("POST", "/api/foundation/v1/explorations/{kind}/complete"),
}


def routes() -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            out.add((method, route.path))
    return out


def main() -> int:
    current = routes()
    missing = sorted(REQUIRED - current)
    if missing:
        print("FOUNDATION_CONTRACT_MISSING")
        for method, path in missing:
            print(f"- {method} {path}")
        return 1
    print(f"FOUNDATION_CONTRACT_OK routes={len(REQUIRED)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
