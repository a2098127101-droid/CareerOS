from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass

import httpx


@dataclass
class Sample:
    ok: bool
    status: int
    latency_ms: float


async def run(args) -> dict:
    sem = asyncio.Semaphore(args.concurrency)
    timeout = httpx.Timeout(args.timeout)
    samples: list[Sample] = []
    headers = {"Accept": "application/json"}
    if args.bearer:
        headers["Authorization"] = f"Bearer {args.bearer}"

    async with httpx.AsyncClient(base_url=args.base_url.rstrip("/"), timeout=timeout, headers=headers) as client:
        async def one(_: int):
            async with sem:
                started = time.perf_counter()
                try:
                    response = await client.request(args.method, args.path)
                    samples.append(Sample(response.is_success, response.status_code, (time.perf_counter() - started) * 1000))
                except Exception:
                    samples.append(Sample(False, 0, (time.perf_counter() - started) * 1000))
        await asyncio.gather(*(one(i) for i in range(args.requests)))

    latencies = sorted(x.latency_ms for x in samples)
    def pct(p: float) -> float:
        if not latencies:
            return 0.0
        index = min(len(latencies) - 1, max(0, round((len(latencies) - 1) * p)))
        return latencies[index]
    return {
        "base_url": args.base_url,
        "path": args.path,
        "method": args.method,
        "requests": len(samples),
        "concurrency": args.concurrency,
        "success": sum(1 for x in samples if x.ok),
        "errors": sum(1 for x in samples if not x.ok),
        "error_rate": round(sum(1 for x in samples if not x.ok) / max(1, len(samples)), 4),
        "latency_ms": {
            "avg": round(statistics.fmean(latencies), 2) if latencies else 0,
            "p50": round(pct(0.50), 2),
            "p95": round(pct(0.95), 2),
            "p99": round(pct(0.99), 2),
            "max": round(max(latencies), 2) if latencies else 0,
        },
        "status_counts": {str(code): sum(1 for x in samples if x.status == code) for code in sorted({x.status for x in samples})},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Small HTTP load-test harness for staging certification. Do not treat local results as production capacity proof.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--path", default="/live")
    parser.add_argument("--method", default="GET")
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--bearer", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    result = asyncio.run(run(args))
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(text + "\n", encoding="utf-8", newline="\n")
    return 0 if result["errors"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
