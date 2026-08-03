#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ROOT_DIR}/.env.production}"
COMPOSE_FILE="${ROOT_DIR}/docker-compose.production.yml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.production.example and replace every CHANGE_ME value." >&2
  exit 1
fi

if grep -Eq '(^|=)CHANGE_ME|example\.com|example\.invalid' "$ENV_FILE"; then
  echo "Production environment still contains placeholder values." >&2
  grep -En 'CHANGE_ME|example\.com|example\.invalid' "$ENV_FILE" >&2 || true
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required=(
  DOMAIN STORAGE_DOMAIN ACME_EMAIL PUBLIC_BASE_URL ALLOWED_ORIGINS APP_SECRET_KEY
  POSTGRES_OWNER_PASSWORD POSTGRES_APP_PASSWORD REDIS_PASSWORD
  MINIO_ROOT_USER MINIO_ROOT_PASSWORD S3_BUCKET
  EMBEDDING_BASE_URL EMBEDDING_API_KEY EMBEDDING_MODEL
  SMTP_HOST EMAIL_FROM BOOTSTRAP_SUPERADMIN_EMAIL BOOTSTRAP_SUPERADMIN_PASSWORD
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required production variable: $name" >&2
    exit 1
  fi
done

if [[ ${#APP_SECRET_KEY} -lt 32 ]]; then
  echo "APP_SECRET_KEY must contain at least 32 characters." >&2
  exit 1
fi

compose=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

"${compose[@]}" config --quiet
"${compose[@]}" build --pull api worker migrate certifier
"${compose[@]}" up -d postgres redis minio
"${compose[@]}" up --no-deps minio-init
"${compose[@]}" up --no-deps migrate
"${compose[@]}" up -d api worker caddy

for attempt in $(seq 1 60); do
  if curl --fail --silent --show-error "https://${DOMAIN}/live" >/dev/null; then
    break
  fi
  if [[ "$attempt" == "60" ]]; then
    echo "CareerOS did not become live within the expected window." >&2
    "${compose[@]}" ps
    "${compose[@]}" logs --tail=200 api caddy
    exit 1
  fi
  sleep 5
done

curl --fail --silent --show-error "https://${DOMAIN}/live" | python -m json.tool

echo
printf 'CareerOS is live at https://%s\n' "$DOMAIN"
echo "Run the certification profile before declaring the environment verified:"
echo "  docker compose --env-file '$ENV_FILE' -f '$COMPOSE_FILE' --profile certify run --rm certifier"
