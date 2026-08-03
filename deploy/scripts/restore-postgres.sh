#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.production}"
BACKUP_FILE="${1:-}"

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
  echo "Usage: $0 /absolute/path/to/careeros-backup.dump[.age]" >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing environment file: $ENV_FILE" >&2
  exit 1
fi
if [[ "${CONFIRM_RESTORE:-}" != "RESTORE_CAREEROS" ]]; then
  echo "Restore is destructive. Re-run with CONFIRM_RESTORE=RESTORE_CAREEROS." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

work_file="$BACKUP_FILE"
temp_file=""
cleanup() { [[ -n "$temp_file" ]] && rm -f "$temp_file"; }
trap cleanup EXIT

if [[ "$BACKUP_FILE" == *.age ]]; then
  command -v age >/dev/null 2>&1 || { echo "age is required to decrypt this backup" >&2; exit 1; }
  temp_file="$(mktemp --suffix=.dump)"
  age --decrypt --output "$temp_file" "$BACKUP_FILE"
  work_file="$temp_file"
fi

if [[ -f "${BACKUP_FILE}.sha256" ]]; then
  (cd "$(dirname "$BACKUP_FILE")" && sha256sum --check "$(basename "${BACKUP_FILE}.sha256")")
fi

compose=(docker compose --env-file "$ENV_FILE" -f "${ROOT_DIR}/docker-compose.production.yml")
"${compose[@]}" stop api worker

cat "$work_file" | "${compose[@]}" exec -T postgres \
  pg_restore \
    --username "${POSTGRES_OWNER_USER:-careeros_owner}" \
    --dbname "${POSTGRES_DB:-careeros}" \
    --clean \
    --if-exists \
    --no-owner \
    --no-acl \
    --exit-on-error

"${compose[@]}" run --rm postgres-role-init
"${compose[@]}" run --rm migrate
"${compose[@]}" up -d api worker caddy

echo "Restore completed. Run runtime and business certification before reopening traffic."
