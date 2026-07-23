#!/usr/bin/env python3
"""Bulk-ingest a local folder into the v0.4 KnowledgeStore.

Example:
  python scripts/ingest_folder.py ./my_rules --scope global --category competition_rule \
      --authority official --year 2026 --priority 95
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import Settings  # noqa: E402
from app.file_parser import parse_uploaded_file  # noqa: E402
from app.knowledge import KnowledgeStore  # noqa: E402

SUPPORTED = {".docx", ".pdf", ".txt", ".md", ".markdown", ".csv", ".json"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk ingest knowledge files")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--scope", default="global")
    parser.add_argument("--category", default="other")
    parser.add_argument("--authority", default="internal")
    parser.add_argument("--year", default="")
    parser.add_argument("--priority", type=int, default=50)
    parser.add_argument("--tag", action="append", default=[])
    args = parser.parse_args()

    if not args.folder.exists() or not args.folder.is_dir():
        parser.error("folder does not exist or is not a directory")

    settings = Settings()
    store = KnowledgeStore(settings.db_path)
    files = [p for p in args.folder.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED]
    if not files:
        print("No supported files found.")
        return 1

    ok = 0
    failed = 0
    for path in files:
        try:
            content = path.read_bytes()
            text = parse_uploaded_file(path.name, content)
            if not text.strip():
                raise ValueError("no usable text")
            result = store.ingest(
                title=path.stem,
                filename=str(path.relative_to(args.folder)),
                mime_type="",
                text=text,
                scope=args.scope,
                tags=args.tag,
                category=args.category,
                authority=args.authority,
                effective_year=args.year,
                priority=max(0, min(100, args.priority)),
            )
            ok += 1
            print(f"OK  {path.name}: {result['chunk_count']} chunks")
        except Exception as exc:
            failed += 1
            print(f"ERR {path}: {exc}", file=sys.stderr)
    print(f"Done. success={ok}, failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
