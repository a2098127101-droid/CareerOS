from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.core.database import BASELINE_METADATA, schema_health
from scripts.import_snapshot_to_postgres import validate_snapshot


def test_schema_health_detects_missing_then_ready(tmp_path: Path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'schema.db').as_posix()}", future=True)
    health = schema_health(engine)
    assert health["ready"] is False and health["missing"]
    BASELINE_METADATA.create_all(engine)
    health = schema_health(engine)
    assert health["ready"] is True and health["missing"] == []


def test_postgresql_baseline_ddl_compiles_all_tables():
    dialect = postgresql.dialect()
    compiled = [str(CreateTable(t).compile(dialect=dialect)) for t in BASELINE_METADATA.sorted_tables]
    assert len(compiled) == len(BASELINE_METADATA.tables)
    assert any("CREATE TABLE sessions" in ddl for ddl in compiled)
    assert any("CREATE TABLE evidence_claims" in ddl for ddl in compiled)


def test_snapshot_checksum_guard_rejects_corruption(tmp_path: Path):
    table = "tenants"
    payload = '{"tenant_id":"org-a","name":"Organization A"}\n'.encode()
    (tmp_path / f"{table}.jsonl").write_bytes(payload)
    manifest = {
        "format": "careeros-sqlite-snapshot-v1",
        "tables": {table: 1},
        "sha256": {table: hashlib.sha256(payload).hexdigest()},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_snapshot(tmp_path)["tables"][table] == 1
    (tmp_path / f"{table}.jsonl").write_text("corrupted\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum mismatch"):
        validate_snapshot(tmp_path)
