from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path


def _batches(items: list[Path], size: int) -> list[list[Path]]:
    size = max(1, int(size))
    return [items[i : i + size] for i in range(0, len(items), size)]


def run_matrix(root: Path, timeout: int = 180, batch_size: int = 6) -> dict:
    """Run test files in isolated batches.

    A single long-lived pytest process is not reliable for this legacy-compatible
    application because some historical tests intentionally reload process-wide
    configuration. One subprocess per file is safe but unnecessarily slow in CI.
    Small isolated batches preserve lifecycle isolation while keeping the GitHub
    gate comfortably below its timeout.
    """
    tests = sorted((root / "tests").glob("test_*.py"))
    groups = _batches(tests, batch_size)
    results = []
    total_passed = 0
    started = time.time()

    for index, group in enumerate(groups, start=1):
        rels = [path.relative_to(root).as_posix() for path in group]
        t0 = time.time()
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
rc = pytest.main(["-q", *{rels!r}], plugins=[counter])
print(f"CAREEROS_PASSED={{counter.passed}}", flush=True)
os._exit(int(rc))
"""
        try:
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
            passed = int(marker.group(1)) if marker else sum(int(x) for x in re.findall(r"(\d+) passed", output))
            status = "passed" if proc.returncode == 0 else "failed"
            if status == "passed":
                total_passed += passed
            results.append({
                "batch": index,
                "files": rels,
                "status": status,
                "returncode": proc.returncode,
                "passed": passed,
                "duration_seconds": round(time.time() - t0, 2),
                "output_tail": "\n".join(output.strip().splitlines()[-16:]),
            })
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            results.append({
                "batch": index,
                "files": rels,
                "status": "timeout",
                "returncode": None,
                "passed": 0,
                "duration_seconds": round(time.time() - t0, 2),
                "output_tail": "\n".join(output.strip().splitlines()[-16:]),
            })

    failed = [item for item in results if item["status"] != "passed"]
    failed_files = [path for item in failed for path in item["files"]]
    covered_files = [path for item in results for path in item["files"]]
    return {
        "ok": not failed,
        "mode": "isolated_test_file_batches",
        "batch_size": batch_size,
        "batches": len(results),
        "files": len(tests),
        "covered_files": covered_files,
        "passed_tests": total_passed,
        "failed_files": failed_files,
        "duration_seconds": round(time.time() - started, 2),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CareerOS pytest files in small isolated subprocess batches.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--timeout", type=int, default=180, help="Per-batch timeout in seconds.")
    parser.add_argument("--batch-size", type=int, default=6, help="Test files per isolated subprocess.")
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()
    report = run_matrix(args.root.resolve(), timeout=args.timeout, batch_size=args.batch_size)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        target = args.json_out if args.json_out.is_absolute() else args.root / args.json_out
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
