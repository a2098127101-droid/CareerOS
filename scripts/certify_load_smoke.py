from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.load_test import run


async def certify(base_url: str, *, requests: int = 100, concurrency: int = 20, p95_limit_ms: float = 1000.0) -> dict:
    scenarios = []
    for path in ("/live", "/api/health"):
        args = SimpleNamespace(
            base_url=base_url, path=path, method="GET", requests=requests, concurrency=concurrency,
            timeout=15.0, bearer="",
        )
        result = await run(args)
        result["pass"] = result["errors"] == 0 and result["latency_ms"]["p95"] <= p95_limit_ms
        scenarios.append(result)
    ok = all(item["pass"] for item in scenarios)
    return {
        "format": "careeros-load-smoke-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "detail": "basic API load smoke passed" if ok else "basic API load smoke failed threshold",
        "requests_per_scenario": requests,
        "concurrency": concurrency,
        "p95_limit_ms": p95_limit_ms,
        "scenarios": scenarios,
        "note": "This is a staging smoke/load gate, not proof of 100/500/1000 concurrent AI capacity.",
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Measured beta1 staging load smoke. Not a production capacity claim.")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--requests", type=int, default=100)
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--p95-limit-ms", type=float, default=1000.0)
    p.add_argument("--out", default="data/load_smoke_certification.json")
    args = p.parse_args()
    report = asyncio.run(certify(args.base_url, requests=args.requests, concurrency=args.concurrency, p95_limit_ms=args.p95_limit_ms))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
