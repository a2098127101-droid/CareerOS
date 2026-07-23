from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import shlex
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class UploadSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class UploadSecurityReport:
    filename: str
    detected_type: str
    declared_type: str
    archive_entries: int = 0
    archive_uncompressed_bytes: int = 0
    malware_scan: str = "not_configured"


_OFFICE_EXTENSIONS = {".docx": "word/", ".pptx": "ppt/", ".xlsx": "xl/"}
_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".txt", ".md", ".markdown", ".csv", ".json"}


def detect_content_type(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if content.startswith(b"%PDF-"):
        return "application/pdf"
    if content.startswith(b"PK\x03\x04") or content.startswith(b"PK\x05\x06") or content.startswith(b"PK\x07\x08"):
        if ext == ".docx":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if ext == ".pptx":
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if ext == ".xlsx":
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return "application/zip"
    if ext == ".pdf":
        return "application/octet-stream"
    if ext == ".json":
        return "application/json"
    if ext == ".csv":
        return "text/csv"
    if ext in {".txt", ".md"}:
        return "text/plain"
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def _validate_archive(filename: str, content: bytes, *, max_entries: int, max_uncompressed_bytes: int, max_ratio: float) -> tuple[int, int]:
    ext = Path(filename).suffix.lower()
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(content)) as zf:
            infos = zf.infolist()
            if len(infos) > max_entries:
                raise UploadSecurityError(f"archive contains too many entries: {len(infos)} > {max_entries}")
            total_uncompressed = sum(max(0, int(i.file_size)) for i in infos)
            total_compressed = sum(max(1, int(i.compress_size)) for i in infos)
            if total_uncompressed > max_uncompressed_bytes:
                raise UploadSecurityError("archive uncompressed size exceeds policy")
            if total_uncompressed / max(1, total_compressed) > max_ratio:
                raise UploadSecurityError("archive compression ratio exceeds zip-bomb policy")
            names = {i.filename for i in infos}
            if "[Content_Types].xml" not in names:
                raise UploadSecurityError("office archive is missing [Content_Types].xml")
            required_prefix = _OFFICE_EXTENSIONS.get(ext)
            if required_prefix and not any(name.startswith(required_prefix) for name in names):
                raise UploadSecurityError(f"file content does not match extension {ext}")
            return len(infos), total_uncompressed
    except zipfile.BadZipFile as exc:
        raise UploadSecurityError("invalid office archive") from exc


def _run_malware_hook(filename: str, content: bytes, command: str) -> str:
    if not command:
        return "not_configured"
    with tempfile.TemporaryDirectory(prefix="careeros-scan-") as tmp:
        path = Path(tmp) / Path(filename).name
        path.write_bytes(content)
        args = [part.replace("{file}", str(path)) for part in shlex.split(command)]
        if not any(str(path) == x for x in args):
            args.append(str(path))
        proc = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
        if proc.returncode != 0:
            message = (proc.stderr or proc.stdout or "malware scan failed")[:500]
            raise UploadSecurityError(f"malware scanner rejected file: {message}")
        return "clean"


def validate_upload(
    *, filename: str, content: bytes, declared_type: str = "", max_bytes: int,
    max_archive_entries: int = 5000, max_archive_uncompressed_bytes: int = 100 * 1024 * 1024,
    max_archive_ratio: float = 100.0, malware_scan_command: str = "",
) -> UploadSecurityReport:
    safe_name = Path(filename or "upload").name
    ext = Path(safe_name).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise UploadSecurityError(f"unsupported file extension: {ext or '<none>'}")
    if not content:
        raise UploadSecurityError("empty upload")
    if len(content) > max_bytes:
        raise UploadSecurityError("upload exceeds maximum size")
    detected = detect_content_type(safe_name, content)
    archive_entries = 0
    archive_uncompressed = 0
    if ext == ".pdf" and detected != "application/pdf":
        raise UploadSecurityError("PDF magic number mismatch")
    if ext in _OFFICE_EXTENSIONS:
        if detected == "application/zip" or not content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
            raise UploadSecurityError("office file magic number mismatch")
        archive_entries, archive_uncompressed = _validate_archive(
            safe_name, content, max_entries=max_archive_entries,
            max_uncompressed_bytes=max_archive_uncompressed_bytes, max_ratio=max_archive_ratio,
        )
    if ext in {".txt", ".md", ".markdown", ".csv", ".json"}:
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadSecurityError("text upload must be valid UTF-8") from exc
    declared = (declared_type or "").split(";", 1)[0].strip().lower()
    # Browser MIME values are not authoritative, but obvious cross-family mismatches are rejected.
    if declared and declared not in {"application/octet-stream", detected.lower()}:
        if ext == ".csv" and declared in {"text/plain", "application/vnd.ms-excel"}:
            pass
        elif ext in {".txt", ".md", ".markdown"} and declared.startswith("text/"):
            pass
        else:
            raise UploadSecurityError(f"declared MIME type does not match detected content: {declared} != {detected}")
    scan = _run_malware_hook(safe_name, content, malware_scan_command)
    return UploadSecurityReport(
        filename=safe_name, detected_type=detected, declared_type=declared_type or "",
        archive_entries=archive_entries, archive_uncompressed_bytes=archive_uncompressed,
        malware_scan=scan,
    )


class FileAccessSigner:
    def __init__(self, secret: str) -> None:
        if not secret:
            raise ValueError("signing secret is required")
        self.secret = secret.encode("utf-8")

    def issue(self, *, object_id: str, tenant_id: str, ttl_seconds: int = 900) -> dict[str, Any]:
        expires = int(time.time()) + max(30, int(ttl_seconds))
        payload = {"object_id": object_id, "tenant_id": tenant_id, "expires": expires}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
        sig = hmac.new(self.secret, token.encode("ascii"), hashlib.sha256).hexdigest()
        return {"token": f"{token}.{sig}", "expires": expires}

    def verify(self, token: str, *, object_id: str) -> dict[str, Any]:
        try:
            encoded, supplied = token.rsplit(".", 1)
            expected = hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(supplied, expected):
                raise UploadSecurityError("invalid signed file token")
            padded = encoded + "=" * (-len(encoded) % 4)
            payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
            if payload.get("object_id") != object_id:
                raise UploadSecurityError("signed token object mismatch")
            if int(payload.get("expires") or 0) < int(time.time()):
                raise UploadSecurityError("signed file token expired")
            return payload
        except UploadSecurityError:
            raise
        except Exception as exc:
            raise UploadSecurityError("invalid signed file token") from exc
