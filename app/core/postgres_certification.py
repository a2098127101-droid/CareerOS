from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


def schema_manifest_sha256(manifest_path: str | Path | None = None) -> str:
    path = Path(manifest_path) if manifest_path else Path(__file__).resolve().parents[1] / "schema_manifest.json"
    return hashlib.sha256(path.read_bytes()).hexdigest()


def database_fingerprint(database_url: str) -> str:
    """Non-secret fingerprint for binding a certification to a target database endpoint."""
    raw = (database_url or "").replace("postgresql+psycopg://", "postgresql://", 1).replace("postgres://", "postgresql://", 1)
    parsed = urlparse(raw)
    identity = f"{parsed.scheme}|{parsed.hostname or ''}|{parsed.port or 5432}|{parsed.path.lstrip('/')}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def load_certification(path: str | Path, *, database_url: str = "") -> dict:
    target = Path(path)
    if not target.exists():
        return {"valid": False, "reason": "certification file not found", "path": str(target)}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"valid": False, "reason": f"invalid certification file: {exc}", "path": str(target)}
    reasons: list[str] = []
    if data.get("format") != "careeros-postgres-certification-v1":
        reasons.append("unsupported certification format")
    if data.get("schema_manifest_sha256") != schema_manifest_sha256():
        reasons.append("schema manifest changed since certification")
    if database_url and data.get("database_fingerprint") != database_fingerprint(database_url):
        reasons.append("certification belongs to a different database endpoint")
    if not data.get("repository_contract_passed"):
        reasons.append("repository contract probe did not pass")
    return {**data, "valid": not reasons, "reason": "; ".join(reasons), "path": str(target)}


def certification_record(*, database_url: str, checks: list[str]) -> dict:
    return {
        "format": "careeros-postgres-certification-v1",
        "certified_at": datetime.now(timezone.utc).isoformat(),
        "database_fingerprint": database_fingerprint(database_url),
        "schema_manifest_sha256": schema_manifest_sha256(),
        "repository_contract_passed": True,
        "checks": checks,
    }
