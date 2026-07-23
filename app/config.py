from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv_env(name: str, default: str = "") -> tuple[str, ...]:
    raw = os.getenv(name, default)
    return tuple(x.strip() for x in raw.split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    demo_mode: bool = _bool_env("DEMO_MODE", True)
    app_env: str = os.getenv("APP_ENV", "development").strip().lower()
    db_path: str = os.getenv("APP_DB_PATH", "data/agent.db")
    database_url: str = os.getenv("DATABASE_URL", "")
    repository_backend: str = os.getenv("REPOSITORY_BACKEND", "sqlite").strip().lower()
    schema_bootstrap_mode: str = os.getenv("SCHEMA_BOOTSTRAP_MODE", "legacy").strip().lower()
    postgres_certification_file: str = os.getenv("POSTGRES_CERTIFICATION_FILE", "data/postgres_certification.json")
    app_secret_key: str = os.getenv("APP_SECRET_KEY", "change-me-in-production")
    admin_token: str = os.getenv("ADMIN_TOKEN", "")
    auth_required: bool = _bool_env("AUTH_REQUIRED", False)
    allow_self_registration: bool = _bool_env("ALLOW_SELF_REGISTRATION", False)
    cookie_secure: bool = _bool_env("COOKIE_SECURE", False)
    session_ttl_hours: int = int(os.getenv("SESSION_TTL_HOURS", "168"))
    allowed_origins: tuple[str, ...] = _csv_env("ALLOWED_ORIGINS", "")
    max_upload_bytes: int = int(os.getenv("MAX_UPLOAD_BYTES", str(12 * 1024 * 1024)))
    rag_top_k: int = int(os.getenv("RAG_TOP_K", "5"))
    rag_max_chars: int = int(os.getenv("RAG_MAX_CHARS", "9000"))
    llm_retry_attempts: int = int(os.getenv("LLM_RETRY_ATTEMPTS", "2"))
    llm_retry_backoff_seconds: float = float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "0.8"))
    llm_circuit_failure_threshold: int = int(os.getenv("LLM_CIRCUIT_FAILURE_THRESHOLD", "5"))
    llm_circuit_cooldown_seconds: int = int(os.getenv("LLM_CIRCUIT_COOLDOWN_SECONDS", "60"))

    # Development/demo bootstrap only. Production should use env-injected one-time bootstrap credentials or the CLI.
    auto_seed_demo_users: bool = _bool_env("AUTO_SEED_DEMO_USERS", True)
    bootstrap_tenant_id: str = os.getenv("BOOTSTRAP_TENANT_ID", "demo-org")
    bootstrap_tenant_name: str = os.getenv("BOOTSTRAP_TENANT_NAME", "CareerOS Demo Organization")

    # Product commercialization / domain preset
    product_preset: str = os.getenv("PRODUCT_PRESET", "career_development").strip() or "career_development"
    product_name: str = os.getenv("PRODUCT_NAME", "CareerOS").strip() or "CareerOS"

    # Semantic retrieval. Defaults to the offline deterministic fallback.
    embedding_provider: str = os.getenv("EMBEDDING_PROVIDER", "local_hash").strip().lower()
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "").strip()
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "local-hash-v1").strip()
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "256"))
    embedding_timeout_seconds: int = int(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "60"))
    embedding_max_batch_size: int = int(os.getenv("EMBEDDING_MAX_BATCH_SIZE", "64"))
    embedding_max_retries: int = int(os.getenv("EMBEDDING_MAX_RETRIES", "2"))
    embedding_retry_backoff_seconds: float = float(os.getenv("EMBEDDING_RETRY_BACKOFF_SECONDS", "0.5"))

    # File storage. Local is appropriate for development; S3-compatible is intended for production.
    storage_provider: str = os.getenv("STORAGE_PROVIDER", "local").strip().lower()
    storage_local_root: str = os.getenv("STORAGE_LOCAL_ROOT", "data/uploads")
    s3_endpoint: str = os.getenv("S3_ENDPOINT", "")
    # Optional browser-facing endpoint for presigned URLs when the SDK uses a private/internal endpoint.
    s3_public_endpoint: str = os.getenv("S3_PUBLIC_ENDPOINT", "").strip()
    # Optional certifier-only network endpoint. The certifier rewrites the URL transport target while
    # preserving the original Host header so the public presigned signature is still validated.
    s3_certification_fetch_endpoint: str = os.getenv("S3_CERTIFICATION_FETCH_ENDPOINT", "").strip()
    s3_bucket: str = os.getenv("S3_BUCKET", "")
    s3_access_key: str = os.getenv("S3_ACCESS_KEY", "")
    s3_secret_key: str = os.getenv("S3_SECRET_KEY", "")
    s3_region: str = os.getenv("S3_REGION", "auto")
    # Distributed runtime state / background jobs. Memory/in-process remain local-development defaults.
    runtime_state_backend: str = os.getenv("RUNTIME_STATE_BACKEND", "memory").strip().lower()
    redis_url: str = os.getenv("REDIS_URL", "").strip()
    background_job_backend: str = os.getenv("BACKGROUND_JOB_BACKEND", "inprocess").strip().lower()
    background_job_workers: int = int(os.getenv("BACKGROUND_JOB_WORKERS", "2"))
    background_job_ttl_seconds: int = int(os.getenv("BACKGROUND_JOB_TTL_SECONDS", "86400"))
    background_job_max_attempts: int = int(os.getenv("BACKGROUND_JOB_MAX_ATTEMPTS", "3"))

    # Private file delivery and upload security.
    file_signed_url_ttl_seconds: int = int(os.getenv("FILE_SIGNED_URL_TTL_SECONDS", "900"))
    upload_max_archive_entries: int = int(os.getenv("UPLOAD_MAX_ARCHIVE_ENTRIES", "5000"))
    upload_max_archive_uncompressed_bytes: int = int(os.getenv("UPLOAD_MAX_ARCHIVE_UNCOMPRESSED_BYTES", str(100 * 1024 * 1024)))
    upload_max_archive_ratio: float = float(os.getenv("UPLOAD_MAX_ARCHIVE_RATIO", "100"))
    malware_scan_command: str = os.getenv("MALWARE_SCAN_COMMAND", "").strip()

    # Observability foundation. Sentry and OpenTelemetry exporters remain optional adapters.
    sentry_dsn: str = os.getenv("SENTRY_DSN", "").strip()
    otel_service_name: str = os.getenv("OTEL_SERVICE_NAME", "careeros-api").strip() or "careeros-api"
    observability_certification_url: str = os.getenv("OBSERVABILITY_CERTIFICATION_URL", "").strip()
    json_logs: bool = _bool_env("JSON_LOGS", True)

    # Public URLs and outbound email. Console provider is development-only and never claims external delivery.
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").strip().rstrip("/")
    email_provider: str = os.getenv("EMAIL_PROVIDER", "console").strip().lower()
    email_from: str = os.getenv("EMAIL_FROM", "").strip()
    email_outbox_path: str = os.getenv("EMAIL_OUTBOX_PATH", "data/email_outbox.jsonl").strip()
    smtp_host: str = os.getenv("SMTP_HOST", "").strip()
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "").strip()
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = _bool_env("SMTP_USE_TLS", True)
    smtp_use_ssl: bool = _bool_env("SMTP_USE_SSL", False)
    smtp_timeout_seconds: int = int(os.getenv("SMTP_TIMEOUT_SECONDS", "20"))

    # Runtime certification report generated by scripts/certify_runtime.py.
    runtime_certification_file: str = os.getenv("RUNTIME_CERTIFICATION_FILE", "data/runtime_certification.json").strip()
    runtime_certification_max_age_hours: int = int(os.getenv("RUNTIME_CERTIFICATION_MAX_AGE_HOURS", "24"))
    business_certification_file: str = os.getenv("BUSINESS_CERTIFICATION_FILE", "data/business_certification.json").strip()
    business_certification_max_age_hours: int = int(os.getenv("BUSINESS_CERTIFICATION_MAX_AGE_HOURS", "24"))

    # Privacy / third-party model data minimization. Enabled by default in production.
    pii_redaction_enabled: bool = _bool_env("PII_REDACTION_ENABLED", os.getenv("APP_ENV", "development").strip().lower() == "production")
    privacy_delete_executor_enabled: bool = _bool_env("PRIVACY_DELETE_EXECUTOR_ENABLED", False)

    # Billing remains sandbox/mock-only in beta1 unless a real provider adapter is implemented later.
    billing_enabled: bool = _bool_env("BILLING_ENABLED", False)
    billing_provider: str = os.getenv("BILLING_PROVIDER", "mock").strip().lower()
    billing_webhook_secret: str = os.getenv("BILLING_WEBHOOK_SECRET", "")

    bootstrap_superadmin_email: str = os.getenv("BOOTSTRAP_SUPERADMIN_EMAIL", "")
    bootstrap_superadmin_password: str = os.getenv("BOOTSTRAP_SUPERADMIN_PASSWORD", "")

    # Backward compatibility with v0.3 .env
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")

    @property
    def llm_enabled(self) -> bool:
        return not self.demo_mode

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def validate_runtime(self) -> list[str]:
        errors: list[str] = []
        if self.is_production:
            if not self.auth_required:
                errors.append("AUTH_REQUIRED must be true in production")
            if self.app_secret_key in {"", "change-me-in-production", "replace-with-a-long-random-secret"} or len(self.app_secret_key) < 32:
                errors.append("APP_SECRET_KEY must be a strong random secret (>=32 chars) in production")
            if not self.allowed_origins:
                errors.append("ALLOWED_ORIGINS must be explicitly configured in production")
            if not self.cookie_secure:
                errors.append("COOKIE_SECURE must be true in production")
            if self.database_url and not self.database_url.startswith(("postgresql://", "postgres://")):
                errors.append("DATABASE_URL must use PostgreSQL in production when configured")
            # Production demo/evaluation mode may still use SQLite for compatibility tests.
            # Real production (DEMO_MODE=false) is fail-closed until PostgreSQL repositories are selected.
            if not self.demo_mode:
                if self.repository_backend != "postgresql":
                    errors.append("REPOSITORY_BACKEND must be postgresql in production when DEMO_MODE=false")
                if not self.database_url:
                    errors.append("DATABASE_URL is required in production when DEMO_MODE=false")
            if self.embedding_provider in {"openai_compatible", "bge_compatible", "jina_compatible", "private_api"} and not (self.embedding_base_url and self.embedding_api_key and self.embedding_model):
                errors.append("EMBEDDING_BASE_URL / EMBEDDING_API_KEY / EMBEDDING_MODEL are required for semantic embeddings")
            if self.storage_provider == "s3" and not (self.s3_bucket and self.s3_access_key and self.s3_secret_key):
                errors.append("S3_BUCKET / S3_ACCESS_KEY / S3_SECRET_KEY are required when STORAGE_PROVIDER=s3")
            if not self.demo_mode:
                if self.runtime_state_backend != "redis" or not self.redis_url:
                    errors.append("RUNTIME_STATE_BACKEND=redis and REDIS_URL are required in non-demo production")
                if self.background_job_backend != "redis":
                    errors.append("BACKGROUND_JOB_BACKEND=redis is required in non-demo production")
                if self.storage_provider != "s3":
                    errors.append("STORAGE_PROVIDER=s3 is required in non-demo production")
            if self.billing_enabled and self.billing_provider == "mock":
                errors.append("BILLING_PROVIDER=mock cannot be used for enabled real billing in production")
            if not self.demo_mode and self.email_provider == "console":
                errors.append("EMAIL_PROVIDER=console cannot be used in non-demo production")
            if self.email_provider == "smtp" and (not self.smtp_host or not self.email_from):
                errors.append("SMTP_HOST and EMAIL_FROM are required when EMAIL_PROVIDER=smtp")
            # Legacy ADMIN_TOKEN may remain unset when authenticated super-admin is used; no fail-open admin endpoints are allowed.
        return errors
