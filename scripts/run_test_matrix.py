from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


def run_matrix(root: Path, timeout: int = 90) -> dict:
    tests = sorted((root / "tests").glob("test_*.py"))
    results = []
    total_passed = 0
    started = time.time()
    for path in tests:
        rel = path.relative_to(root).as_posix()
        t0 = time.time()
        try:
            runner = f"""
import os
import pytest

class _PassedCounter:
    def __init__(self):
        self.passed = 0

    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.passed:
            self.passed += 1

counter = _PassedCounter()
rc = pytest.main(["-q", {rel!r}], plugins=[counter])
print(f"CAREEROS_PASSED={{counter.passed}}", flush=True)
os._exit(int(rc))
"""
            proc = subprocess.run(
                [sys.executable, "-c", runner],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
            output = proc.stdout
            marker = re.search(r"CAREEROS_PASSED=(\d+)", output)
            # Keep the summary fallback for older pytest versions and for
            # diagnostic compatibility with historical matrix output.
            passed = (
                int(marker.group(1))
                if marker
                else sum(int(x) for x in re.findall(r"(\d+) passed", output))
            )
            status = "passed" if proc.returncode == 0 else "failed"
            total_passed += passed if proc.returncode == 0 else 0
            results.append({
                "file": rel,
                "status": status,
                "returncode": proc.returncode,
                "passed": passed,
                "duration_seconds": round(time.time() - t0, 2),
                "output_tail": "\n".join(output.strip().splitlines()[-12:]),
            })
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            results.append({
                "file": rel,
                "status": "timeout",
                "returncode": None,
                "passed": 0,
                "duration_seconds": round(time.time() - t0, 2),
                "output_tail": "\n".join(output.strip().splitlines()[-12:]),
            })
    failed = [r for r in results if r["status"] != "passed"]
    return {
        "ok": not failed,
        "mode": "isolated_test_file_subprocesses",
        "files": len(results),
        "passed_tests": total_passed,
        "failed_files": [r["file"] for r in failed],
        "duration_seconds": round(time.time() - started, 2),
        "results": results,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Run each CareerOS pytest file in an isolated subprocess to avoid shared lifecycle state.")
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--timeout", type=int, default=90)
    p.add_argument("--json-out", type=Path, default=None)
    args = p.parse_args()
    report = run_matrix(args.root.resolve(), timeout=args.timeout)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        target = args.json_out if args.json_out.is_absolute() else args.root / args.json_out
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
