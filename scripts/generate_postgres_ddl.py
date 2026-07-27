from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
_ROOT = _BootstrapPath(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.database import BASELINE_METADATA


def generate() -> str:
    dialect = postgresql.dialect()
    parts = ["-- CareerOS v1.5 Domain Intelligence PostgreSQL baseline generated from schema_manifest.json", ""]
    for table in BASELINE_METADATA.sorted_tables:
        parts.append(str(CreateTable(table).compile(dialect=dialect)).rstrip() + ";")
        parts.append("")
    for table in BASELINE_METADATA.sorted_tables:
        for index in table.indexes:
            parts.append(str(CreateIndex(index).compile(dialect=dialect)).rstrip() + ";")
    return "\n".join(parts).strip() + "\n"


if __name__ == "__main__":
    target = Path("deploy/postgresql_baseline.sql")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate(), encoding="utf-8")
    print(target)
