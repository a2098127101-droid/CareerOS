from __future__ import annotations

import json
from pathlib import Path

from app.core.postgres_certification import (
    certification_record,
    database_fingerprint,
    load_certification,
    schema_manifest_sha256,
)


def test_database_fingerprint_does_not_depend_on_credentials():
    a = database_fingerprint("postgresql://user-a:secret-a@db.example.test:5432/careeros")
    b = database_fingerprint("postgresql://user-b:secret-b@db.example.test:5432/careeros")
    c = database_fingerprint("postgresql://user-b:secret-b@db.example.test:5432/other")
    assert a == b
    assert a != c


def test_certification_is_bound_to_database_and_schema(tmp_path: Path):
    url = "postgresql://user:secret@db.example.test:5432/careeros"
    target = tmp_path / "cert.json"
    record = certification_record(database_url=url, checks=["repository_contract"])
    target.write_text(json.dumps(record), encoding="utf-8")
    loaded = load_certification(target, database_url=url)
    assert loaded["valid"] is True
    assert loaded["schema_manifest_sha256"] == schema_manifest_sha256()
    wrong = load_certification(target, database_url="postgresql://user:secret@db.example.test:5432/other")
    assert wrong["valid"] is False
    assert "different database" in wrong["reason"]
