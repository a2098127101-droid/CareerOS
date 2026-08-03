from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIRED = (
    "Dockerfile",
    "requirements.lock",
    "alembic.ini",
    "app/main.py",
    "app/static/projects.html",
    "app/static/student.html",
    "app/static/teacher.html",
    "app/static/governance.html",
    "deploy/docker-compose.production.yml",
    "alembic/versions/0012_project_tenant_rls.py",
    "deploy/.env.production.example",
    "deploy/Caddyfile",
    "deploy/README_PRODUCTION.md",
)
EXCLUDED_DIRS = {
    ".git",
    ".github-cache",
    ".idea",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "backups",
    "dist",
    "build",
}
EXCLUDED_NAMES = {
    ".env",
    ".env.production",
    ".env.staging",
    "agent.db",
    "email_outbox.jsonl",
    "runtime_certification.json",
    "business_certification.json",
    "postgres_certification.json",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log", ".dump", ".age", ".sqlite", ".sqlite3"}
SENSITIVE_FRAGMENTS = (
    "/data/uploads/",
    "/data/backups/",
    "/data/certifications/",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a sanitized CareerOS production release ZIP.")
    parser.add_argument("--version", default="v1.0.0-rc1")
    parser.add_argument("--out-dir", default="dist")
    return parser.parse_args()


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def should_include(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    parts = relative.parts
    if any(part in EXCLUDED_DIRS for part in parts):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    normalized = "/" + relative.as_posix().lower() + "/"
    if any(fragment in normalized for fragment in SENSITIVE_FRAGMENTS):
        return False
    if path.name.startswith(".env.") and path.name not in {".env.example", ".env.production.example", ".env.staging.example"}:
        return False
    return path.is_file()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_required() -> None:
    missing = [item for item in DEFAULT_REQUIRED if not (ROOT / item).is_file()]
    if missing:
        raise SystemExit(f"Release package is incomplete; missing: {', '.join(missing)}")


def validate_no_runtime_secrets(paths: list[Path]) -> None:
    forbidden = {".env.production", ".env.staging", "agent.db"}
    violations = [path.relative_to(ROOT).as_posix() for path in paths if path.name in forbidden]
    if violations:
        raise SystemExit(f"Sensitive runtime files selected for release: {violations}")


def build(version: str, out_dir: Path) -> tuple[Path, Path]:
    validate_required()
    paths = sorted((path for path in ROOT.rglob("*") if should_include(path)), key=lambda item: item.as_posix())
    validate_no_runtime_secrets(paths)

    package_name = f"CareerOS-{version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{package_name}.zip"
    manifest_path = out_dir / f"{package_name}.manifest.json"
    commit = git_value("rev-parse", "HEAD")
    ref = git_value("rev-parse", "--abbrev-ref", "HEAD")
    generated_at = datetime.now(timezone.utc).isoformat()

    files: list[dict[str, object]] = []
    for path in paths:
        content = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(content),
                "sha256": sha256_bytes(content),
            }
        )

    manifest = {
        "package": package_name,
        "version": version,
        "generated_at": generated_at,
        "git_commit": commit,
        "git_ref": ref,
        "file_count": len(files),
        "files": files,
        "release_boundary": {
            "contains_secrets": False,
            "contains_runtime_database": False,
            "contains_student_data": False,
            "runtime_verified": False,
            "verification_required_after_deployment": True,
        },
    }
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    manifest_path.write_bytes(manifest_bytes)

    deterministic_time = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in paths:
            relative = PurePosixPath(package_name) / PurePosixPath(path.relative_to(ROOT).as_posix())
            info = zipfile.ZipInfo(relative.as_posix(), date_time=deterministic_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            if path.suffix in {".sh", ".cmd"} or path.name in {"OPEN_CareerOS.cmd"}:
                info.external_attr = 0o100755 << 16
            archive.writestr(info, path.read_bytes())
        manifest_info = zipfile.ZipInfo(
            (PurePosixPath(package_name) / "RELEASE_MANIFEST.json").as_posix(),
            date_time=deterministic_time,
        )
        manifest_info.compress_type = zipfile.ZIP_DEFLATED
        manifest_info.external_attr = 0o100644 << 16
        archive.writestr(manifest_info, manifest_bytes)

    checksum_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    checksum_path.write_text(f"{sha256_bytes(zip_path.read_bytes())}  {zip_path.name}\n", encoding="utf-8")
    return zip_path, manifest_path


def main() -> None:
    args = parse_args()
    zip_path, manifest_path = build(args.version, ROOT / args.out_dir)
    print(json.dumps({"zip": str(zip_path), "manifest": str(manifest_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
