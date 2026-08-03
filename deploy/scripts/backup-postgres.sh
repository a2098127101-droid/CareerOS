#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-${ROOT_DIR}/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing environment file: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="${BACKUP_DIR}/careeros-${timestamp}.dump"
checksum="${archive}.sha256"

compose=(docker compose --env-file "$ENV_FILE" -f "${ROOT_DIR}/docker-compose.production.yml")

"${compose[@]}" exec -T postgres \
  pg_dump \
    --username "${POSTGRES_OWNER_USER:-careeros_owner}" \
    --dbname "${POSTGRES_DB:-careeros}" \
    --format custom \
    --no-owner \
    --no-acl \
  > "$archive"

sha256sum "$archive" > "$checksum"
chmod 600 "$archive" "$checksum"

if command -v age >/dev/null 2>&1 && [[ -n "${BACKUP_AGE_RECIPIENT:-}" ]]; then
  age --recipient "$BACKUP_AGE_RECIPIENT" --output "${archive}.age" "$archive"
  rm -f "$archive"
  archive="${archive}.age"
  sha256sum "$archive" > "${archive}.sha256"
  rm -f "$checksum"
fi

find "$BACKUP_DIR" -type f -name 'careeros-*' -mtime "+${RETENTION_DAYS}" -delete

echo "Backup created: $archive"
