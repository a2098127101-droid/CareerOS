from __future__ import annotations

import argparse
from pathlib import Path


def select(root: Path, *, groups: int, index: int) -> list[Path]:
    tests = sorted((root / "tests").glob("test_*.py"))
    if groups < 1:
        raise ValueError("groups must be >= 1")
    if index < 0 or index >= groups:
        raise ValueError("index must satisfy 0 <= index < groups")
    # Contiguous deterministic groups make local reproduction straightforward.
    base, remainder = divmod(len(tests), groups)
    start = index * base + min(index, remainder)
    size = base + (1 if index < remainder else 0)
    return tests[start : start + size]


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a deterministic subset of CareerOS pytest files.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--groups", type=int, default=6)
    parser.add_argument("--index", type=int, required=True)
    args = parser.parse_args()
    selected = select(args.root.resolve(), groups=args.groups, index=args.index)
    if not selected:
        raise SystemExit("selected test group is empty")
    print(" ".join(path.relative_to(args.root.resolve()).as_posix() for path in selected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
