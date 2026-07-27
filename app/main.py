from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from uuid import uuid4
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.security import APIKeyCookie
from fastapi.staticfiles import StaticFiles

from .agent_service import CareerAgentService
from .auth_store import AuthStore, Principal
from .authz import AuthorizationError, require_session_access
from .lifecycle import workflow_snapshot
from .bootstrap import bootstrap_model_config
from .config import Settings
from .domain_profile import get_domain_profile
from .domain_intelligence import DomainIntelligenceService
from .embedding_gateway import EmbeddingConfig, EmbeddingGateway
from .retrieval import RerankerConfig, RerankerGateway
from .evidence_verification import EvidenceVerificationService
from .rag_evaluation import RAGEvalCase, evaluate_rag
from .pgvector_backend import pgvector_capabilities
from .storage import LocalStorageAdapter, S3CompatibleStorageAdapter, StorageRegistry, StorageError
from .file_security import FileAccessSigner, UploadSecurityError, validate_upload
from .runtime_state import build_rate_limiter, redis_capabilities
from .background_jobs import build_job_manager
from .job_handlers import register_background_handlers
from .observability import RuntimeMetrics, configure_observability
from .billing import build_billing_provider
from .emailing import EmailDeliveryError, build_email_provider, invitation_email, password_reset_email
from .runtime_certification import RuntimeCertification, load_runtime_certification, write_certification
from .business_certification import load_business_certification
from .data_lifecycle import DataLifecycleService
from .evidence_lock import audit_evidence
from .file_parser import parse_uploaded_file
from .migrations import migration_status, run_migrations
from .llm_gateway import LLMGatewayError
from .models import (
    ChatMessage,
    AITaskCreateRequest,
    AITaskUpdateRequest,
    ChatRequest,
    DraftRequest,
    KnowledgeSearchRequest,
    KnowledgeTextIngest,
    KnowledgeSourceUpdate,
    RAGEvaluationRequest, EvidenceVerificationRequest, ManualClaimVerificationRequest, JobMatchRequest,
    ProfileExtractRequest,
    ReviewRequest,
    ReviseRequest,
    SessionState,
    TeacherFeedbackRequest,
    TeacherNoteRequest,
    RegisterRequest, LoginRequest, PasswordChangeRequest, PasswordResetRequest, PasswordResetConfirm,
    TenantCreateRequest, TenantBrandingRequest, TenantProductConfigRequest, UserCreateRequest, ClassCreateRequest, ClassMemberRequest,
    InvitationCreateRequest, InvitationAcceptRequest, UserLifecycleUpdateRequest, MembershipRoleUpdateRequest,
    TrackInput,
    TrackRecommendRequest,
)
from .rule_engine import recommend_track
from .repositories import RepositoryContainer
from .repositories.parity import CORE_PARITY
from .core.database import database_capabilities
from .core.postgres_certification import load_certification
from .domain.roles import canonical_role
from .domain.profile import ParticipantProfile
from .workflow_templates import get_workflow_template, list_workflow_templates, workflow_template_from_record
from .artifact_templates import resolve_artifact_template, list_artifact_templates, artifact_template_from_record
from .job_intelligence import JobIntelligenceService
from .routers.privacy import build_privacy_router
from .routers.commercial import build_commercial_router
from .routers.templates import build_template_admin_router
from .routers.unified_runtime import build_unified_runtime_router
from .routers.workspace import build_workspace_router
from .routers.domain_intelligence import build_domain_intelligence_router
from .routers.system import build_system_router
from .routers.model_admin import build_model_admin_router
from .api_versioning import register_v1_compatibility_aliases
from .tenant_context import clear_tenant_context, set_tenant_context

settings = Settings()
_runtime_errors = settings.validate_runtime()
if _runtime_errors:
    raise RuntimeError("Production security validation failed: " + "; ".join(_runtime_errors))

# Legacy SQLite migrations remain active only for the SQLite compatibility runtime.
# PostgreSQL schema ownership is Alembic-only and startup is fail-closed if the schema is missing.
_applied_migrations = run_migrations(settings.db_path) if settings.repository_backend != "postgresql" else []
product_profile = get_domain_profile(settings.product_preset)
embedding_gateway = EmbeddingGateway(EmbeddingConfig(
    provider=settings.embedding_provider, base_url=settings.embedding_base_url, api_key=settings.embedding_api_key,
    model=settings.embedding_model, dimensions=settings.embedding_dimensions, timeout_seconds=settings.embedding_timeout_seconds,
    max_batch_size=settings.embedding_max_batch_size, max_retries=settings.embedding_max_retries,
    retry_backoff_seconds=settings.embedding_retry_backoff_seconds,
))
reranker_gateway = RerankerGateway(RerankerConfig(
    provider=settings.reranker_provider,
    base_url=settings.reranker_base_url,
    api_key=settings.reranker_api_key,
    model=settings.reranker_model,
    timeout_seconds=settings.reranker_timeout_seconds,
    max_retries=settings.reranker_max_retries,
    retry_backoff_seconds=settings.reranker_retry_backoff_seconds,
))
# Repository container centralizes persistence wiring. v1.0-beta1 keeps SQLite local compatibility
# while the full SQLAlchemy repository surface can be wired to PostgreSQL after Alembic provisioning.
if settings.repository_backend == "postgresql":
    repositories = RepositoryContainer.build_postgresql(
        db_path=settings.db_path,
        database_url=settings.database_url,
        app_secret_key=settings.app_secret_key,
        session_ttl_hours=settings.session_ttl_hours,
        embedding_gateway=embedding_gateway,
        reranker_gateway=reranker_gateway,
        app_env=settings.app_env,
    )
else:
    repositories = RepositoryContainer.build_sqlite(
        db_path=settings.db_path,
        database_url=settings.database_url,
        app_secret_key=settings.app_secret_key,
        session_ttl_hours=settings.session_ttl_hours,
        embedding_gateway=embedding_gateway,
        reranker_gateway=reranker_gateway,
        app_env=settings.app_env,
    )
store = repositories.sessions
model_store = repositories.models
knowledge_store = repositories.knowledge
job_store = repositories.jobs
job_intelligence = JobIntelligenceService(job_store)
artifact_store = repositories.artifacts
evidence_store = repositories.evidence
evidence_graph = repositories.evidence_graph
evidence_verifier = EvidenceVerificationService(embedding_gateway)
workflow_store = repositories.workflows
collaboration_store = repositories.collaboration
auth_store = repositories.identity
commercial_store = repositories.commercial
template_registry = repositories.templates
unified_runtime_store = repositories.runtime_entities
domain_intelligence_store = repositories.domain_intelligence
domain_intelligence_service = DomainIntelligenceService(domain_intelligence_store, evidence_verifier, job_intelligence)
billing_runtime = build_billing_provider(settings.billing_provider, webhook_secret=settings.billing_webhook_secret)
email_runtime = build_email_provider(
    settings.email_provider,
    outbox_path=settings.email_outbox_path,
    smtp_host=settings.smtp_host, smtp_port=settings.smtp_port, smtp_username=settings.smtp_username,
    smtp_password=settings.smtp_password, email_from=settings.email_from, smtp_use_tls=settings.smtp_use_tls,
    smtp_use_ssl=settings.smtp_use_ssl, timeout_seconds=settings.smtp_timeout_seconds,
)
storage_registry = repositories.storage_registry
if settings.storage_provider == "s3":
    object_storage = S3CompatibleStorageAdapter(
        endpoint=settings.s3_endpoint, bucket=settings.s3_bucket, access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key, region=settings.s3_region, public_endpoint=settings.s3_public_endpoint,
    )
else:
    object_storage = LocalStorageAdapter(settings.storage_local_root)

data_lifecycle = DataLifecycleService(
    sessions=store, artifacts=artifact_store, evidence=evidence_store, evidence_graph=evidence_graph,
    workflows=workflow_store, collaboration=collaboration_store, identity=auth_store,
    storage_registry=storage_registry, object_storage=object_storage,
)

file_signer = FileAccessSigner(settings.app_secret_key)
rate_limiter = build_rate_limiter(backend=settings.runtime_state_backend, redis_url=settings.redis_url)
background_jobs = build_job_manager(
    backend=settings.background_job_backend, redis_url=settings.redis_url,
    max_workers=settings.background_job_workers, ttl_seconds=settings.background_job_ttl_seconds,
    max_attempts=settings.background_job_max_attempts,
)

register_background_handlers(background_jobs, knowledge_store=knowledge_store)
observability_state = configure_observability(
    json_logs=settings.json_logs, sentry_dsn=settings.sentry_dsn, environment=settings.app_env,
    service_name=settings.otel_service_name,
)
runtime_metrics = RuntimeMetrics()
logger = logging.getLogger("careeros.api")
bootstrap_model_config(model_store, settings)
agents = CareerAgentService(settings, model_store, knowledge_store, job_store, commercial_store=commercial_store)

# Safe local demo accounts. Never auto-seeded in production.
if settings.auto_seed_demo_users and not settings.is_production:
    auth_store.ensure_tenant(settings.bootstrap_tenant_id, settings.bootstrap_tenant_name, tenant_type="organization", product_preset="career_development")
    demo_class_id = "demo-default"
    try:
        demo_class = auth_store.get_class(demo_class_id)
        if demo_class.get("tenant_id") != settings.bootstrap_tenant_id:
            demo_class_id = "demo-default-org"
            auth_store.create_class(settings.bootstrap_tenant_id, "Default Group", class_id=demo_class_id)
    except KeyError:
        auth_store.create_class(settings.bootstrap_tenant_id, "Default Group", class_id=demo_class_id)
    for email, password, name, role in [
        ("admin@demo.local", "CareerOS-Demo-123!", "Demo Organization Admin", "school_admin"),
        ("teacher@demo.local", "CareerOS-Demo-123!", "Demo Advisor", "teacher"),
        ("student@demo.local", "CareerOS-Demo-123!", "Demo User", "student"),
        ("super@demo.local", "CareerOS-Demo-123!", "Platform Admin", "super_admin"),
    ]:
        try:
            user = auth_store.ensure_user(email=email,password=password,display_name=name,tenant_id=settings.bootstrap_tenant_id,role=role)
            if role in {"teacher","student"}:
                auth_store.add_class_member(class_id=demo_class_id,tenant_id=settings.bootstrap_tenant_id,user_id=user["user_id"],role=role)
        except Exception:
            pass
    commercial_store.ensure_subscription(settings.bootstrap_tenant_id, "professional")
    commercial_store.set_plan(settings.bootstrap_tenant_id, "professional")
elif settings.bootstrap_superadmin_email and settings.bootstrap_superadmin_password:
    auth_store.ensure_tenant(settings.bootstrap_tenant_id, settings.bootstrap_tenant_name, tenant_type="organization", product_preset=settings.product_preset)
    auth_store.ensure_user(
        email=settings.bootstrap_superadmin_email, password=settings.bootstrap_superadmin_password,
        display_name="CareerOS Super Admin", tenant_id=settings.bootstrap_tenant_id, role="super_admin"
    )

app = FastAPI(
    title=f"{settings.product_name} · AI Career Development Platform",
    version="1.5.1-release-hardening",
    description=(
        "CareerOS Production API. Canonical new integrations should use `/api/v1`; "
        "unversioned `/api/*` endpoints remain compatibility aliases during migration."
    ),
    openapi_tags=[
        {"name": "Authentication", "description": "Server-side session authentication."},
        {"name": "Student workspace", "description": "Participant-owned workflow and artifacts."},
        {"name": "Advisor operations", "description": "Authorized cohort operations."},
        {"name": "AI administration", "description": "Model, retrieval, and job intelligence administration."},
        {"name": "System", "description": "Health and operational readiness."},
    ],
)
origins = list(settings.allowed_origins) if settings.allowed_origins else (["*"] if not settings.is_production else [])
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=bool(settings.auth_required),
    allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],
    allow_headers=["Content-Type","Authorization","X-Admin-Token","X-Request-ID","X-CSRF-Token","X-CareerOS-Billing-Signature","Idempotency-Key"],
)

def _rate_allowed(key: tuple[str, str], limit: int, window_seconds: int = 60) -> bool:
    return rate_limiter.allow(scope=key[1], key=key[0], limit=limit, window_seconds=window_seconds)


@app.middleware("http")
async def security_observability_and_rate_limit(request: Request, call_next):
    clear_tenant_context()
    path = request.url.path
    request_id = request.headers.get("X-Request-ID") or f"REQ-{uuid4().hex[:20]}"
    started = time.perf_counter()
    # Cookie-authenticated mutation requests are origin-checked in production to reduce CSRF risk.
    if settings.is_production and settings.auth_required and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.cookies.get(AUTH_COOKIE):
            origin = (request.headers.get("origin") or "").rstrip("/")
            allowed = {o.rstrip("/") for o in settings.allowed_origins}
            if not origin or origin not in allowed:
                return JSONResponse({"detail": "CSRF origin validation failed"}, status_code=403, headers={"X-Request-ID": request_id})
    if request.method != "OPTIONS":
        host = request.client.host if request.client else "unknown"
        if path == "/api/auth/login" and not _rate_allowed((host, "login"), 10, 60):
            return JSONResponse({"detail": "too many login attempts"}, status_code=429, headers={"X-Request-ID": request_id})
        legacy_ai = {"/api/chat", "/api/chat/stream", "/api/draft/generate", "/api/draft/generate/stream", "/api/review", "/api/review/stream", "/api/revise"}
        workspace_ai_limits = {
            "/api/workspace/v1/ai/coach": 30,
            "/api/workspace/v1/ai/interview/evaluate": 10,
            "/api/workspace/v1/ai/ppt/review": 5,
        }
        ai_limit = 60 if path in legacy_ai else workspace_ai_limits.get(path)
        if ai_limit is not None and not _rate_allowed((host, "ai:" + path), ai_limit, 60):
            return JSONResponse({"detail": {"code": "ai_rate_limit_exceeded", "limit": ai_limit, "window_seconds": 60}}, status_code=429, headers={"X-Request-ID": request_id})
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        status_code = 500
        latency_ms = (time.perf_counter() - started) * 1000
        runtime_metrics.observe(method=request.method, path=path, status_code=status_code, latency_ms=latency_ms)
        logger.exception("request failed", extra={"request_id": request_id, "path": path, "method": request.method, "status_code": status_code, "latency_ms": round(latency_ms, 2)})
        clear_tenant_context()
        raise
    latency_ms = (time.perf_counter() - started) * 1000
    runtime_metrics.observe(method=request.method, path=path, status_code=status_code, latency_ms=latency_ms)
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), payment=()")
    clear_tenant_context()
    return response

STAGE_ORDER = {"profile": 1, "track": 2, "draft": 3, "review": 4, "revised": 5}
STAGE_LABELS = {"profile": "建立画像", "track": "目标确认", "draft": "成果初稿", "review": "严格评审", "revised": "完成修订"}


AUTH_COOKIE = "careeros_session"
session_cookie = APIKeyCookie(
    name=AUTH_COOKIE,
    scheme_name="CareerOSSession",
    description="HttpOnly CareerOS session cookie returned by `/api/auth/login`.",
    auto_error=False,
)


def _demo_principal() -> Principal:
    return Principal(
        user_id="demo-local",
        email="local@demo.invalid",
        display_name="Local Demo",
        tenant_id=settings.bootstrap_tenant_id,
        role="super_admin",
        authenticated=False,
    )


def current_principal(
    request: Request,
    token: str | None = Depends(session_cookie),
) -> Principal:
    principal = auth_store.resolve_session(token)
    if principal:
        set_tenant_context(principal.tenant_id, platform_admin=principal.is_super_admin)
        return principal
    if not settings.auth_required:
        principal = _demo_principal()
        set_tenant_context(principal.tenant_id, platform_admin=principal.is_super_admin)
        return principal
    raise HTTPException(status_code=401, detail="authentication required")


def require_roles(*roles: str):
    allowed = {canonical_role(r) for r in roles}
    def dep(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.is_super_admin or canonical_role(principal.role) in allowed:
            return principal
        raise HTTPException(status_code=403, detail="insufficient permissions")
    return dep


def _domain_for_tenant(tenant_id: str):
    """Resolve tenant product behavior without trusting browser-provided labels."""
    try:
        tenant = auth_store.get_tenant(tenant_id)
        return get_domain_profile(tenant.get("product_preset") or settings.product_preset)
    except Exception:
        return product_profile

def _workflow_preset_id(tenant_id: str) -> str:
    return _domain_for_tenant(tenant_id).profile_id


def _require_entitlement(tenant_id: str, feature: str) -> None:
    if settings.demo_mode:
        return
    if not bool(commercial_store.entitlement(tenant_id, feature, False)):
        raise HTTPException(status_code=403, detail=f"feature not available on current plan: {feature}")


def _require_artifact_version_quota(state: SessionState) -> None:
    if settings.demo_mode:
        return
    limit = int(commercial_store.entitlement(state.tenant_id, "artifact_versions", 0) or 0)
    if not limit:
        return
    current_count = len(artifact_store.list_session(state.session_id, tenant_id=state.tenant_id, all_versions=True))
    if current_count >= limit:
        raise HTTPException(status_code=403, detail=f"artifact version quota reached: {limit}")


def _authorize_state(state: SessionState, principal: Principal, *, write: bool = False) -> None:
    if not principal.authenticated:
        return
    try:
        require_session_access(principal, state, auth_store, write=write)
    except AuthorizationError:
        auth_store.audit(
            tenant_id=principal.tenant_id, user_id=principal.user_id, action="session_access_denied",
            resource_type="session", resource_id=state.session_id, success=False,
        )
        raise HTTPException(status_code=403, detail="session access denied")


def _tenant_for(principal: Principal, requested: str | None = None) -> str:
    if principal.is_super_admin and requested:
        return requested
    return principal.tenant_id


def _require_admin_legacy(x_admin_token: str | None, principal: Principal) -> None:
    """Legacy token is only accepted in local/demo mode. Production admin access is role-based and fail-closed."""
    if principal.authenticated:
        if not principal.is_super_admin:
            raise HTTPException(status_code=403, detail="super admin required")
        return
    if settings.auth_required:
        raise HTTPException(status_code=401, detail="authentication required")
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(status_code=401, detail="管理员 Token 无效")


def _resolved_workflow_template(tenant_id: str, preset_id: str):
    record = template_registry.active_workflow(tenant_id=tenant_id, preset_id=preset_id)
    return workflow_template_from_record(record) if record else get_workflow_template(preset_id)


def _resolved_artifact_template(document_type: str | None, tenant_id: str, preset_id: str):
    record = template_registry.resolve_artifact(document_type, tenant_id=tenant_id, preset_id=preset_id)
    return artifact_template_from_record(record) if record else resolve_artifact_template(document_type, preset_id)


@app.get("/api/product/config")
def product_config(principal: Principal = Depends(current_principal)):
    tenant = None
    preset = product_profile
    if principal.authenticated:
        try:
            tenant = auth_store.get_tenant(principal.tenant_id)
            preset = get_domain_profile(tenant.get("product_preset") or settings.product_preset)
        except Exception:
            tenant = None
    return {
        "product_name": settings.product_name,
        "preset": preset.profile_id,
        "workflow_template": _resolved_workflow_template((tenant or {}).get("tenant_id") or (principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id), preset.profile_id).template_id,
        "subtitle": preset.product_subtitle,
        "labels": {
            "organization": preset.organization_label, "advisor": preset.advisor_label, "member": preset.member_label,
            "cohort": preset.cohort_label, "artifact": preset.artifact_label,
        },
        "features": {"competition_template": preset.enable_competition_template, "school_features": preset.enable_school_features, "capabilities": sorted(preset.features)},
        "tenant": tenant,
    }


@app.get("/api/product/workflow-templates")
def product_workflow_templates(principal: Principal = Depends(current_principal)):
    current = _domain_for_tenant(principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id)
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    templates = list_workflow_templates()
    custom = template_registry.list_workflows(tenant_id=tenant_id, preset_id="" if (principal.is_super_admin if principal.authenticated else False) else current.profile_id)
    custom_payload = [{**x, "source": "tenant"} for x in custom]
    builtins = [{**x, "source": "builtin"} for x in templates if ((principal.is_super_admin if principal.authenticated else True) or x["preset_id"] == current.profile_id)]
    return {
        "current_preset": current.profile_id,
        "current_template_id": _resolved_workflow_template(tenant_id, current.profile_id).template_id,
        "templates": builtins + custom_payload,
    }


@app.get("/api/product/artifact-templates")
def product_artifact_templates(principal: Principal = Depends(current_principal)):
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    preset = _domain_for_tenant(tenant_id).profile_id
    builtin = [{**x, "source": "builtin"} for x in list_artifact_templates(preset)]
    custom = [{**x, "source": "tenant"} for x in template_registry.list_artifacts(tenant_id=tenant_id, preset_id=preset)]
    return {"preset": preset, "templates": builtin + custom}


@app.post("/api/auth/register")
def auth_register(req: RegisterRequest):
    if not settings.allow_self_registration:
        raise HTTPException(status_code=403, detail="self registration is disabled")
    try:
        user = auth_store.create_user(
            email=req.email,password=req.password,display_name=req.display_name,
            tenant_id=req.tenant_id,role="student"
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok":True,"user":user}


@app.post("/api/auth/login")
def auth_login(req: LoginRequest, response: Response, request: Request):
    try:
        principal, token = auth_store.authenticate(req.email, req.password, tenant_id=req.tenant_id, role=req.role)
    except PermissionError:
        auth_store.audit(tenant_id=req.tenant_id or "global", user_id="", action="login_failed", success=False, details={"email": req.email}, ip_address=(request.client.host if request.client else ""))
        raise HTTPException(status_code=401, detail="邮箱、密码或组织身份无效")
    response.set_cookie(
        AUTH_COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
        path="/",
    )
    auth_store.audit(tenant_id=principal.tenant_id, user_id=principal.user_id, action="login", success=True, ip_address=(request.client.host if request.client else ""))
    commercial_store.track(tenant_id=principal.tenant_id, user_id=principal.user_id, event_name="login")
    return {"ok": True, "user": {**principal.__dict__, "canonical_role": canonical_role(principal.role)}, "redirect": {"participant": "/participant", "advisor": "/advisor", "organization_admin": "/admin", "platform_admin": "/admin"}.get(canonical_role(principal.role), "/")}


@app.post("/api/auth/logout")
def auth_logout(response: Response, request: Request):
    token = request.cookies.get(AUTH_COOKIE)
    principal = auth_store.resolve_session(token)
    auth_store.revoke_session(token)
    response.delete_cookie(AUTH_COOKIE, path="/")
    if principal:
        auth_store.audit(tenant_id=principal.tenant_id, user_id=principal.user_id, action="logout")
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(principal: Principal = Depends(current_principal)):
    if not principal.authenticated:
        return {"authenticated": False, "demo_mode": True, "user": {**principal.__dict__, "canonical_role": canonical_role(principal.role)}}
    user = auth_store.get_user(principal.user_id, include_memberships=True)
    return {"authenticated": True, "user": {**principal.__dict__, "canonical_role": canonical_role(principal.role)}, "profile": user}


@app.post("/api/auth/password/change")
def auth_change_password(req: PasswordChangeRequest, principal: Principal = Depends(current_principal)):
    if not principal.authenticated:
        raise HTTPException(status_code=403, detail="not available in demo anonymous mode")
    try:
        auth_store.change_password(principal.user_id, req.current_password, req.new_password)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "message": "密码已更新，请重新登录"}


@app.post("/api/auth/password/reset/request")
def auth_password_reset_request(req: PasswordResetRequest):
    token = auth_store.request_password_reset(req.email)
    payload = {"ok": True, "message": "如账号存在，重置流程已创建。"}
    if token:
        reset_url = f"{settings.public_base_url}/login#reset={token}"
        subject, body = password_reset_email(product_name=settings.product_name, reset_url=reset_url, ttl_minutes=30)
        try:
            delivery = email_runtime.send(to=req.email.strip().lower(), subject=subject, text=body)
            payload["delivery"] = {"provider": delivery.provider, "accepted": delivery.accepted, "message_id": delivery.message_id, "detail": delivery.detail}
        except EmailDeliveryError as exc:
            logger.error("password reset email delivery failed", extra={"email_provider": settings.email_provider, "error": str(exc)})
            payload["delivery"] = {"provider": settings.email_provider, "accepted": False, "detail": "delivery failed"}
        if not settings.is_production:
            payload["debug_reset_token"] = token
    return payload


@app.post("/api/auth/password/reset/confirm")
def auth_password_reset_confirm(req: PasswordResetConfirm):
    try:
        auth_store.reset_password(req.token, req.new_password)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


@app.post("/api/auth/invitations/accept")
def auth_accept_invitation(req: InvitationAcceptRequest):
    try:
        user = auth_store.accept_invitation(req.token, req.password, req.display_name)
        return {"ok": True, "user": user}
    except (PermissionError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/tenants")
def admin_list_tenants(principal: Principal = Depends(require_roles("super_admin"))):
    return {"tenants": auth_store.list_tenants()}


@app.post("/api/admin/tenants")
def admin_create_tenant(req: TenantCreateRequest, principal: Principal = Depends(require_roles("super_admin"))):
    tenant = auth_store.ensure_tenant(req.tenant_id, req.name, tenant_type=req.tenant_type, product_preset=req.product_preset)
    commercial_store.ensure_subscription(req.tenant_id, "free")
    return {"ok": True, "tenant": tenant, "subscription": commercial_store.subscription(req.tenant_id)}


@app.put("/api/admin/tenants/{tenant_id}/branding")
def admin_update_branding(tenant_id: str, req: TenantBrandingRequest, principal: Principal = Depends(require_roles("school_admin"))):
    if not principal.is_super_admin and principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant access denied")
    try:
        return {"ok": True, "tenant": auth_store.update_tenant_branding(tenant_id, req.branding)}
    except KeyError:
        raise HTTPException(status_code=404, detail="tenant not found")


@app.put("/api/admin/tenants/{tenant_id}/product-config")
def admin_update_product_config(tenant_id: str, req: TenantProductConfigRequest, principal: Principal = Depends(require_roles("school_admin"))):
    if not principal.is_super_admin and principal.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="tenant access denied")
    try:
        tenant = auth_store.update_tenant_product_config(tenant_id, tenant_type=req.tenant_type, product_preset=req.product_preset, settings=req.settings)
        return {"ok": True, "tenant": tenant}
    except KeyError:
        raise HTTPException(status_code=404, detail="tenant not found")


@app.get("/api/admin/users")
def admin_list_users(role: str = Query(default=""), tenant_id: str = Query(default=""), principal: Principal = Depends(require_roles("school_admin"))):
    target = _tenant_for(principal, tenant_id or None)
    return {"users": auth_store.list_users(target, role=role or None)}


@app.post("/api/admin/users")
def admin_create_user(req: UserCreateRequest, principal: Principal = Depends(require_roles("school_admin"))):
    target = _tenant_for(principal, req.tenant_id)
    if canonical_role(req.role) == "platform_admin" and not principal.is_super_admin:
        raise HTTPException(status_code=403, detail="only super admin can create super admin")
    try:
        user = auth_store.create_user(email=req.email,password=req.password,display_name=req.display_name,tenant_id=target,role=req.role)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "user": user}


@app.get("/api/admin/invitations")
def admin_list_invitations(tenant_id: str = Query(default=""), include_closed: bool = Query(default=False), principal: Principal = Depends(require_roles("school_admin"))):
    target = _tenant_for(principal, tenant_id or None)
    return {"invitations": auth_store.list_invitations(target, include_closed=include_closed)}


@app.post("/api/admin/invitations")
def admin_create_invitation(req: InvitationCreateRequest, principal: Principal = Depends(require_roles("school_admin"))):
    if canonical_role(req.role) == "platform_admin" and not principal.is_super_admin:
        raise HTTPException(status_code=403, detail="only platform admin can invite platform admin")
    try:
        invitation = auth_store.create_invitation(email=req.email, tenant_id=principal.tenant_id, role=req.role, invited_by=principal.user_id, display_name=req.display_name, ttl_hours=req.ttl_hours)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    invite_url = f"{settings.public_base_url}/login#invite={invitation['token']}"
    subject, body = invitation_email(product_name=settings.product_name, invite_url=invite_url, role=invitation["role"], expires_at=invitation["expires_at"])
    try:
        delivery = email_runtime.send(to=invitation["email"], subject=subject, text=body)
        delivery_payload = {"provider": delivery.provider, "accepted": delivery.accepted, "message_id": delivery.message_id, "detail": delivery.detail}
    except EmailDeliveryError as exc:
        logger.error("invitation email delivery failed", extra={"email_provider": settings.email_provider, "error": str(exc)})
        delivery_payload = {"provider": settings.email_provider, "accepted": False, "detail": "delivery failed"}
    # Raw tokens are kept only for local/debug workflows. Production clients receive delivery metadata, not the token.
    public_invitation = dict(invitation)
    if settings.is_production:
        public_invitation.pop("token", None)
    return {"ok": True, "invitation": public_invitation, "delivery": delivery_payload}


@app.delete("/api/admin/invitations/{invitation_id}")
def admin_revoke_invitation(invitation_id: str, principal: Principal = Depends(require_roles("school_admin"))):
    try:
        auth_store.revoke_invitation(invitation_id, principal.tenant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="invitation not found")
    return {"ok": True}


@app.patch("/api/admin/users/{user_id}/status")
def admin_update_user_status(user_id: str, req: UserLifecycleUpdateRequest, principal: Principal = Depends(require_roles("school_admin"))):
    try:
        target_user = auth_store.get_user(user_id, include_memberships=True)
        if any(canonical_role(m.get("role", "")) == "platform_admin" for m in target_user.get("memberships", [])) and not principal.is_super_admin:
            raise HTTPException(status_code=403, detail="only platform admin can modify platform admin lifecycle")
        return {"ok": True, "user": auth_store.set_user_status(user_id=user_id, tenant_id=principal.tenant_id, status=req.status)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/api/admin/users/{user_id}/role")
def admin_update_user_role(user_id: str, req: MembershipRoleUpdateRequest, principal: Principal = Depends(require_roles("school_admin"))):
    if canonical_role(req.role) == "platform_admin" and not principal.is_super_admin:
        raise HTTPException(status_code=403, detail="only platform admin can assign platform admin")
    try:
        target_user = auth_store.get_user(user_id, include_memberships=True)
        if any(canonical_role(m.get("role", "")) == "platform_admin" for m in target_user.get("memberships", [])) and not principal.is_super_admin:
            raise HTTPException(status_code=403, detail="only platform admin can modify platform admin membership")
        return {"ok": True, "user": auth_store.change_membership_role(user_id=user_id, tenant_id=principal.tenant_id, role=req.role)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/admin/groups")
@app.get("/api/admin/classes")
def admin_list_classes(tenant_id: str = Query(default=""), principal: Principal = Depends(require_roles("school_admin", "teacher"))):
    target = _tenant_for(principal, tenant_id or None)
    classes = auth_store.list_classes(target)
    if canonical_role(principal.role) == "advisor" and not principal.is_super_admin:
        allowed = auth_store.user_class_ids(principal.user_id, target, role="teacher")
        classes = [c for c in classes if c["class_id"] in allowed]
    return {"classes": classes}


@app.post("/api/admin/groups")
@app.post("/api/admin/classes")
def admin_create_class(req: ClassCreateRequest, principal: Principal = Depends(require_roles("school_admin"))):
    target = _tenant_for(principal, req.tenant_id)
    try:
        return {"ok": True, "class": auth_store.create_class(target, req.name)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/admin/groups/{class_id}/members")
@app.post("/api/admin/classes/{class_id}/members")
def admin_add_class_member(class_id: str, req: ClassMemberRequest, principal: Principal = Depends(require_roles("school_admin"))):
    tenant_id = principal.tenant_id if not principal.is_super_admin else auth_store.get_class(class_id)["tenant_id"]
    try:
        auth_store.add_class_member(class_id=class_id,tenant_id=tenant_id,user_id=req.user_id,role=req.role)
    except (KeyError, PermissionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


app.include_router(build_system_router(
    settings=settings,
    agents=agents,
    knowledge_store=knowledge_store,
    job_store=job_store,
    embedding_gateway=embedding_gateway,
    rate_limiter=rate_limiter,
    background_jobs=background_jobs,
    observability_state=observability_state,
    repositories=repositories,
    product_profile=product_profile,
))


@app.get("/api/admin/system/metrics")
def runtime_metrics_snapshot(principal: Principal = Depends(require_roles("school_admin"))):
    return {"metrics": runtime_metrics.snapshot(), "observability": observability_state}


@app.post("/api/sessions", response_model=SessionState)
def create_session(principal: Principal = Depends(current_principal)):
    if principal.authenticated and canonical_role(principal.role) not in {"participant", "platform_admin"}:
        raise HTTPException(status_code=403, detail="student account required to create a student session")
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    owner_user_id = principal.user_id if principal.authenticated and canonical_role(principal.role) == "participant" else ""
    class_id = "default"
    if owner_user_id:
        class_ids = sorted(auth_store.user_class_ids(owner_user_id, tenant_id, role="student"))
        if class_ids:
            class_id = class_ids[0]
    state = store.create(tenant_id=tenant_id, student_user_id=owner_user_id, class_id=class_id, student_id=owner_user_id or "")
    state.messages.append(ChatMessage(
        role="assistant",
        content="你好，我是 CareerOS AI Coach。你可以从目标方向、已有经历、技能、作品或当前困惑开始；信息不完整也没关系，我会先建立可验证画像，再逐步推进定位、能力差距、行动计划与成果物。",
        action="welcome",
    ))
    store.save(state)
    workflow_store.ensure(state, preset_id=_workflow_preset_id(state.tenant_id))
    commercial_store.track(tenant_id=tenant_id, user_id=owner_user_id, session_id=state.session_id, event_name="session_created")
    return state


def get_state(session_id: str) -> SessionState:
    try:
        return store.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session not found")


def get_authorized_state(session_id: str, principal: Principal, *, write: bool = False) -> SessionState:
    state = get_state(session_id)
    _authorize_state(state, principal, write=write)
    return state


def _evidence_context(session_id: str, state: SessionState | None = None) -> str:
    ledger = evidence_store.build_context(session_id, tenant_id=(state.tenant_id if state else None))
    if ledger.strip():
        return ledger
    return state.profile.evidence_text if state else ""


def _teacher_guidance(session_id: str, state: SessionState | None = None) -> str:
    items = collaboration_store.list_feedback(session_id, status="open", tenant_id=(state.tenant_id if state else None))
    return "\n".join(f"[{x['feedback_id']}] {x['teacher_name']}：{x['content']}" for x in reversed(items[:8]))


def _artifact_kind(document_type: str | None, revised: bool = False, *, tenant_id: str = "", preset_id: str = "career_development") -> str:
    base = _resolved_artifact_template(document_type, tenant_id or settings.bootstrap_tenant_id, preset_id).kind
    return f"{base}_revision" if revised else base


def _save_artifact_version(state: SessionState, content: str, revised: bool = False, metadata: dict | None = None) -> dict:
    kind = _artifact_kind(state.document_type, revised=revised, tenant_id=state.tenant_id, preset_id=_workflow_preset_id(state.tenant_id))
    title = (state.document_type or "作品") + (" · 修订版" if revised else " · 初稿")
    links = evidence_store.link_text(state.session_id, content, tenant_id=state.tenant_id)
    previous = artifact_store.latest(state.session_id, kind, tenant_id=state.tenant_id)
    artifact_template = _resolved_artifact_template(state.document_type, state.tenant_id, _workflow_preset_id(state.tenant_id))
    artifact_metadata = dict(metadata or {})
    artifact_metadata.setdefault("artifact_template_id", artifact_template.template_id)
    artifact_metadata.setdefault("renderer", artifact_template.renderer)
    artifact_metadata.setdefault("review_rubric", artifact_template.review_rubric)
    artifact = artifact_store.create_version(
        session_id=state.session_id,
        kind=kind,
        title=title,
        content=content,
        metadata=artifact_metadata,
        evidence_links=links,
        tenant_id=state.tenant_id,
        owner_user_id=state.student_user_id,
        source=(metadata or {}).get("source", "unknown"),
    )
    trace = evidence_graph.trace_artifact_version(
        tenant_id=state.tenant_id, session_id=state.session_id, artifact_id=artifact["artifact_id"],
        version_id=artifact["version_id"], content=content,
        evidence_items=evidence_store.list_session(state.session_id, tenant_id=state.tenant_id),
    )
    artifact["trace_summary"] = trace
    if previous and previous.get("version_id") != artifact.get("version_id"):
        latest_review = evidence_graph.latest_review(state.session_id, tenant_id=state.tenant_id)
        feedback_ids = [x["feedback_id"] for x in collaboration_store.list_feedback(state.session_id, status="open", tenant_id=state.tenant_id)]
        evidence_graph.link_revision(
            tenant_id=state.tenant_id, session_id=state.session_id,
            previous_version_id=previous.get("version_id", ""), new_version_id=artifact.get("version_id", ""),
            review_id=(latest_review or {}).get("review_id", ""), feedback_ids=feedback_ids,
        )
    return artifact


def _workflow_for_state(state: SessionState) -> dict:
    kinds = {x["kind"].split("_revision")[0] for x in artifact_store.list_session(state.session_id, tenant_id=state.tenant_id)}
    try:
        return workflow_store.sync_from_state(state, artifact_kinds=kinds, preset_id=_workflow_preset_id(state.tenant_id))
    except KeyError:
        return workflow_store.ensure(state, artifact_kinds=kinds, preset_id=_workflow_preset_id(state.tenant_id))


@app.get("/api/sessions/{session_id}", response_model=SessionState)
def read_session(session_id: str, principal: Principal = Depends(current_principal)):
    return get_authorized_state(session_id, principal)


@app.get("/api/sessions/{session_id}/participant-profile")
def participant_profile(session_id: str, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal)
    return {"session_id": state.session_id, "profile": ParticipantProfile.from_legacy(state.profile).model_dump()}


@app.post("/api/sessions/{session_id}/profile/extract", response_model=SessionState)
async def extract_profile(session_id: str, req: ProfileExtractRequest, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal, write=True)
    evidence_store.add(session_id, "manual", "画像补充", req.text, tenant_id=state.tenant_id, owner_user_id=state.student_user_id)
    state.profile = await agents.extract_profile(req.text, state.profile, tenant_id=state.tenant_id)
    state.stage = "profile"
    store.save(state)
    workflow_store.sync_from_state(state, source_type="profile_extract", preset_id=_workflow_preset_id(state.tenant_id))
    commercial_store.track(tenant_id=state.tenant_id, user_id=state.student_user_id, session_id=state.session_id, event_name="profile_updated")
    return state


@app.post("/api/track/recommend")
def track_recommend(req: TrackRecommendRequest, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(req.session_id, principal, write=True)
    rec = recommend_track(req.signals)
    state.track_recommendation = rec
    state.track = rec.recommended_track
    state.stage = "track"
    store.save(state)
    workflow_store.sync_from_state(state, source_type="track_recommend", preset_id=_workflow_preset_id(state.tenant_id))
    return {"state": state, "recommendation": rec, "workflow": _workflow_for_state(state)}


@app.post("/api/draft/generate")
async def generate_draft(req: DraftRequest, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(req.session_id, principal, write=True)
    state.document_type = req.document_type
    draft, audit = await agents.generate_draft(
        state, req.document_type, req.extra_instructions,
        student_evidence=_evidence_context(state.session_id, state),
        teacher_guidance=_teacher_guidance(state.session_id, state),
    )
    state.draft = draft
    state.review = None
    state.revised_draft = ""
    state.stage = "draft"
    _require_artifact_version_quota(state)
    artifact = _save_artifact_version(state, draft, revised=False, metadata={"source": "writer_agent"})
    commercial_store.track(tenant_id=state.tenant_id, user_id=state.student_user_id, session_id=state.session_id, event_name="artifact_created", properties={"kind": artifact.get("kind"), "version": artifact.get("version")})
    collaboration_store.complete_matching(state.session_id, "generate_draft", tenant_id=state.tenant_id)
    collaboration_store.ensure_task("完成严格评审", "review_draft", session_id=state.session_id, tenant_id=state.tenant_id, source="workflow")
    store.save(state)
    return {"draft": draft, "evidence_audit": audit, "artifact": artifact, "workflow": _workflow_for_state(state), "state": state}


@app.post("/api/review")
async def review(req: ReviewRequest, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(req.session_id, principal, write=True)
    _require_entitlement(state.tenant_id, "advanced_review")
    draft = req.draft if req.draft is not None else state.draft
    if not draft.strip():
        raise HTTPException(status_code=400, detail="draft is empty")
    report = await agents.review(state, draft, student_evidence=_evidence_context(state.session_id, state))
    state.draft = draft
    state.review = report
    state.stage = "review"
    collaboration_store.complete_matching(state.session_id, "review_draft", tenant_id=state.tenant_id)
    collaboration_store.ensure_task("按评审意见完成修订", "revise_draft", session_id=state.session_id, tenant_id=state.tenant_id, priority="high" if report.total_score < 70 else "normal", source="reviewer", payload={"score": report.total_score})
    current_artifact = artifact_store.latest(state.session_id, _artifact_kind(state.document_type, tenant_id=state.tenant_id, preset_id=_workflow_preset_id(state.tenant_id)), tenant_id=state.tenant_id)
    review_trace = evidence_graph.record_review(
        tenant_id=state.tenant_id, session_id=state.session_id,
        artifact_id=(current_artifact or {}).get("artifact_id", ""), version_id=(current_artifact or {}).get("version_id", ""),
        report=report.model_dump(), created_by=(principal.user_id if principal.authenticated else "reviewer_agent"),
    )
    store.save(state)
    workflow_store.sync_from_state(state, source_type="review", source_id=review_trace["review_id"], preset_id=_workflow_preset_id(state.tenant_id))
    commercial_store.track(tenant_id=state.tenant_id, user_id=state.student_user_id, session_id=state.session_id, event_name="review_completed", properties={"score": report.total_score})
    return {"review": report, "review_trace": review_trace, "evidence_audit": audit_evidence(draft, state.profile.evidence_text), "workflow": _workflow_for_state(state), "state": state}


@app.post("/api/revise")
async def revise(req: ReviseRequest, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(req.session_id, principal, write=True)
    draft = req.draft if req.draft is not None else state.draft
    report = req.review if req.review is not None else state.review
    if not draft.strip() or report is None:
        raise HTTPException(status_code=400, detail="draft and review are required")
    revised, audit, critic = await agents.revise(
        state, draft, report,
        student_evidence=_evidence_context(state.session_id, state),
        teacher_guidance=_teacher_guidance(state.session_id, state),
    )
    state.revised_draft = revised
    state.stage = "revised"
    _require_artifact_version_quota(state)
    artifact = _save_artifact_version(state, revised, revised=True, metadata={"source": "revision_agent", "score_before": report.total_score})
    collaboration_store.complete_matching(state.session_id, "revise_draft", tenant_id=state.tenant_id)
    store.save(state)
    workflow_store.sync_from_state(state, source_type="artifact_version", source_id=artifact.get("version_id", ""), preset_id=_workflow_preset_id(state.tenant_id))
    commercial_store.track(tenant_id=state.tenant_id, user_id=state.student_user_id, session_id=state.session_id, event_name="revision_completed", properties={"artifact_id": artifact.get("artifact_id"), "version": artifact.get("version")})
    return {"revised_draft": revised, "evidence_audit": audit, "critic": critic, "artifact": artifact, "workflow": _workflow_for_state(state), "state": state}


def _grade_level(grade: str) -> int:
    text = grade or ""
    match = re.search(r"([1-8一二三四五六七八])", text)
    if not match:
        return 2
    mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}
    value = match.group(1)
    return mapping.get(value, int(value) if value.isdigit() else 2)


def _derive_track_signals(state: SessionState) -> TrackInput:
    p = state.profile
    return TrackInput(
        grade_level=_grade_level(p.grade),
        career_goal_clarity=4 if p.target_job else 2,
        internship_count=len(p.internships),
        project_count=len(p.projects),
        has_clear_target_job=bool(p.target_job.strip()),
    )


def _intent(message: str) -> str:
    m = message.strip().lower()
    if ("成长赛道" in m or "就业赛道" in m) and any(k in m for k in ["选择", "确定", "确认", "我要", "参加"]):
        return "confirm_track"
    if any(k in m for k in ["修订", "按意见改", "修改作品", "优化作品", "重新修改"]):
        return "revise"
    if any(k in m for k in ["评分", "评审", "打分", "作品问题", "看看问题"]):
        return "review"
    if any(k in m for k in ["生成初稿", "写简历", "写规划书", "生成作品", "开始写", "帮我写"]):
        return "draft"
    if ("赛道" in m and any(k in m for k in ["推荐", "选", "适合", "哪个"])) or m in {"推荐赛道", "赛道推荐"}:
        return "track"
    return "chat"


@app.post("/api/chat")
async def chat(req: ChatRequest, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(req.session_id, principal, write=True)
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is empty")

    state.messages.append(ChatMessage(role="user", content=message))
    commercial_store.track(tenant_id=state.tenant_id, user_id=state.student_user_id, session_id=state.session_id, event_name="coach_message", properties={"length": len(message)})
    evidence_store.add_chat_candidate(state.session_id, message, tenant_id=state.tenant_id, owner_user_id=state.student_user_id)
    state.profile = await agents.extract_profile(message, state.profile, tenant_id=state.tenant_id)
    action = _intent(message)
    domain = _domain_for_tenant(state.tenant_id)
    # Track selection is a domain-specific workflow. Generic commercial presets never force it.
    if not domain.enable_competition_template and action in {"track", "confirm_track"}:
        action = "chat"
    payload: dict = {}
    refs = []

    if action == "confirm_track":
        chosen = "就业赛道" if "就业赛道" in message else "成长赛道"
        state.track = chosen
        state.stage = "track"
        reply = f"已确认 **{chosen}**。接下来我会按该赛道组织作品结构与评审口径。你可以直接说“帮我生成初稿”。"
        payload["confirmed_track"] = chosen

    elif action == "track":
        rec = recommend_track(_derive_track_signals(state))
        state.track_recommendation = rec
        state.track = rec.recommended_track
        state.stage = "track"
        reasons = "；".join(rec.reasons[:3])
        if rec.recommended_track == "待确认":
            reply = f"两条赛道适配度比较接近：成长赛道 {rec.growth_score}%，就业赛道 {rec.employment_score}%。主要依据：{reasons}。请结合当届资格要求确认，并回复“我选择成长赛道”或“我选择就业赛道”。"
        else:
            reply = f"基于你当前已确认的画像，我更建议 **{rec.recommended_track}**。成长赛道适配度 {rec.growth_score}%，就业赛道适配度 {rec.employment_score}%。主要依据：{reasons}。如认可，请回复“我选择{rec.recommended_track}”；最终仍需以当届官方资格与学校通知核验。"
        payload["recommendation"] = rec.model_dump()

    elif action == "draft":
        if domain.enable_competition_template and state.track == "待确认" and "简历" not in message and "规划书" not in message:
            rec = recommend_track(_derive_track_signals(state))
            state.track_recommendation = rec
            reply = f"在生成作品前先确认赛道。当前成长赛道适配度 {rec.growth_score}%，就业赛道适配度 {rec.employment_score}%。请回复“我选择成长赛道”或“我选择就业赛道”；也可以明确说“生成简历”或“生成职业规划书”。"
            payload["recommendation"] = rec.model_dump()
            state.messages.append(ChatMessage(role="assistant", content=reply, action="track"))
            store.save(state)
            workflow_store.sync_from_state(state, source_type="chat", source_id="track_confirmation_required", preset_id=_workflow_preset_id(state.tenant_id))
            return {"reply": reply, "action": "track", "state": state, "workflow": _workflow_for_state(state), **payload}
        doc_type = "简历" if ("简历" in message or (domain.enable_competition_template and state.track == "就业赛道")) else ("职业规划书" if domain.enable_competition_template else "发展报告")
        state.document_type = doc_type
        draft, audit = await agents.generate_draft(
            state, doc_type, message,
            student_evidence=_evidence_context(state.session_id, state),
            teacher_guidance=_teacher_guidance(state.session_id, state),
        )
        state.draft = draft
        state.review = None
        state.revised_draft = ""
        state.stage = "draft"
        _require_artifact_version_quota(state)
        payload["artifact"] = _save_artifact_version(state, draft, revised=False, metadata={"source": "coach_writer"})
        collaboration_store.complete_matching(state.session_id, "generate_draft", tenant_id=state.tenant_id)
        collaboration_store.ensure_task("完成严格评审", "review_draft", session_id=state.session_id, tenant_id=state.tenant_id, source="workflow")
        display_type = "职业发展报告" if (doc_type in {"职业规划书", "发展报告"} and not domain.enable_competition_template) else doc_type
        reply = f"已生成一版 **{display_type}初稿**。我只调用你已经提供或已验证的事实；缺失信息会保留“待补充”，不会替你虚构经历。下一步可以直接对我说“给这份成果评分”。"
        retrieval_query = (f"{state.track} {doc_type} 评分标准 作品规范 {state.profile.target_job}" if domain.enable_competition_template
                           else f"{display_type} 评价标准 成果规范 目标岗位 {state.profile.target_job}")
        _, refs = agents.retrieve_context(retrieval_query, state)
        payload.update({"draft": draft, "evidence_audit": audit.model_dump()})

    elif action == "review":
        if not state.draft.strip():
            reply = "目前还没有可评审的成果。先告诉我“生成初稿”，或者上传/粘贴已有材料。"
        else:
            report = await agents.review(state, state.draft, student_evidence=_evidence_context(state.session_id, state))
            state.review = report
            state.stage = "review"
            current_artifact = artifact_store.latest(state.session_id, _artifact_kind(state.document_type, tenant_id=state.tenant_id, preset_id=_workflow_preset_id(state.tenant_id)), tenant_id=state.tenant_id)
            payload["review_trace"] = evidence_graph.record_review(
                tenant_id=state.tenant_id, session_id=state.session_id,
                artifact_id=(current_artifact or {}).get("artifact_id", ""), version_id=(current_artifact or {}).get("version_id", ""),
                report=report.model_dump(), created_by=(principal.user_id if principal.authenticated else "reviewer_agent"),
            )
            collaboration_store.complete_matching(state.session_id, "review_draft", tenant_id=state.tenant_id)
            collaboration_store.ensure_task("按评审意见完成修订", "revise_draft", session_id=state.session_id, tenant_id=state.tenant_id, priority="high" if report.total_score < 70 else "normal", source="reviewer", payload={"score": report.total_score})
            reply = f"严格评审已完成：**{report.total_score}/100**。最高优先级不是语言润色，而是先处理：{report.revision_priority[0] if report.revision_priority else '证据链与结构问题'}。你可以继续说“按意见修订”。"
            _, refs = agents.retrieve_context(f"{state.track} 评分标准 评审规则 {state.document_type or ''}", state)
            payload["review"] = report.model_dump()

    elif action == "revise":
        if not state.draft.strip():
            reply = "还没有初稿，无法修订。先生成或导入作品。"
        else:
            if state.review is None:
                state.review = await agents.review(state, state.draft, student_evidence=_evidence_context(state.session_id, state))
                current_artifact = artifact_store.latest(state.session_id, _artifact_kind(state.document_type, tenant_id=state.tenant_id, preset_id=_workflow_preset_id(state.tenant_id)), tenant_id=state.tenant_id)
                payload["review_trace"] = evidence_graph.record_review(
                    tenant_id=state.tenant_id, session_id=state.session_id,
                    artifact_id=(current_artifact or {}).get("artifact_id", ""), version_id=(current_artifact or {}).get("version_id", ""),
                    report=state.review.model_dump(), created_by=(principal.user_id if principal.authenticated else "reviewer_agent"),
                )
            revised, audit, critic = await agents.revise(
                state, state.draft, state.review,
                student_evidence=_evidence_context(state.session_id, state),
                teacher_guidance=_teacher_guidance(state.session_id, state),
            )
            state.revised_draft = revised
            state.stage = "revised"
            _require_artifact_version_quota(state)
            payload["artifact"] = _save_artifact_version(state, revised, revised=True, metadata={"source": "coach_revision", "score_before": state.review.total_score})
            collaboration_store.complete_matching(state.session_id, "revise_draft", tenant_id=state.tenant_id)
            reply = "Critic 复核与修订已完成。修订版已经生成；仍存在的“待补充”表示缺少真实材料，不能由 AI 代填。"
            _, refs = agents.retrieve_context(f"{state.track} 评分标准 作品规范 {state.profile.target_job}", state)
            payload.update({"revised_draft": revised, "critic": critic, "evidence_audit": audit.model_dump()})

    else:
        reply, refs = await agents.coach(state, message)
        open_feedback = collaboration_store.list_feedback(state.session_id, status="open", tenant_id=state.tenant_id)
        if open_feedback:
            latest = open_feedback[0]
            reply = f"Advisor 最新反馈：{latest['content']}\n\n{reply}"
            payload["teacher_feedback"] = latest

    state.messages.append(ChatMessage(role="assistant", content=reply, action=action, knowledge_refs=refs))
    store.save(state)
    workflow_store.sync_from_state(state, source_type="chat", source_id=action, preset_id=_workflow_preset_id(state.tenant_id))
    payload["workflow"] = _workflow_for_state(state)
    return {"reply": reply, "action": action, "state": state, "knowledge_refs": [r.model_dump() for r in refs], **payload}


def _sse_event(event: str, data) -> str:
    payload = json.dumps(jsonable_encoder(data), ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, principal: Principal = Depends(current_principal)):
    async def events():
        yield _sse_event("status", {"stage": "accepted", "message": "Request accepted"})
        yield _sse_event("status", {"stage": "analyzing", "message": "Analyzing context and evidence"})
        await asyncio.sleep(0)
        try:
            result = await chat(req, principal)
            yield _sse_event("result", result)
        except HTTPException as exc:
            yield _sse_event("error", {"status_code": exc.status_code, "detail": exc.detail})
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/draft/generate/stream")
async def generate_draft_stream(req: DraftRequest, principal: Principal = Depends(current_principal)):
    async def events():
        for stage, message in [("evidence", "Collecting verified evidence"), ("retrieval", "Retrieving relevant knowledge"), ("generation", "Generating artifact")]:
            yield _sse_event("status", {"stage": stage, "message": message})
            await asyncio.sleep(0)
        try:
            yield _sse_event("result", await generate_draft(req, principal))
        except HTTPException as exc:
            yield _sse_event("error", {"status_code": exc.status_code, "detail": exc.detail})
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/review/stream")
async def review_stream(req: ReviewRequest, principal: Principal = Depends(current_principal)):
    async def events():
        for stage, message in [("evidence", "Checking evidence trace"), ("evaluation", "Applying review rubric"), ("verification", "Verifying high-risk claims")]:
            yield _sse_event("status", {"stage": stage, "message": message})
            await asyncio.sleep(0)
        try:
            yield _sse_event("result", await review(req, principal))
        except HTTPException as exc:
            yield _sse_event("error", {"status_code": exc.status_code, "detail": exc.detail})
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _validate_upload_security(file: UploadFile, content: bytes):
    try:
        return validate_upload(
            filename=file.filename or "upload", content=content, declared_type=file.content_type or "",
            max_bytes=settings.max_upload_bytes,
            max_archive_entries=settings.upload_max_archive_entries,
            max_archive_uncompressed_bytes=settings.upload_max_archive_uncompressed_bytes,
            max_archive_ratio=settings.upload_max_archive_ratio,
            malware_scan_command=settings.malware_scan_command,
        )
    except UploadSecurityError as exc:
        detail = str(exc)
        status = 413 if "maximum size" in detail or "uncompressed size" in detail else 400
        raise HTTPException(status_code=status, detail=detail)


def _authorize_stored_object(meta: dict, principal: Principal) -> None:
    if principal.is_super_admin:
        return
    if meta.get("tenant_id") != principal.tenant_id:
        raise HTTPException(status_code=404, detail="file not found")
    if meta.get("owner_user_id") in {"", principal.user_id}:
        return
    if meta.get("session_id"):
        try:
            get_authorized_state(meta["session_id"], principal)
            return
        except HTTPException:
            pass
    if canonical_role(principal.role) in {"advisor", "organization_admin"}:
        return
    raise HTTPException(status_code=403, detail="file access denied")


@app.post("/api/files/parse")
async def parse_file(file: UploadFile = File(...), session_id: str = Form(default=""), principal: Principal = Depends(current_principal)):
    content = await file.read()
    security_report = _validate_upload_security(file, content)
    try:
        text = parse_uploaded_file(file.filename or "upload", content)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    evidence = None
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    owner_user_id = principal.user_id if principal.authenticated else ""
    if session_id:
        state = get_authorized_state(session_id, principal, write=True)
        tenant_id = state.tenant_id
        owner_user_id = state.student_user_id
        evidence = evidence_store.add(session_id, "file", file.filename or "上传文件", text, tenant_id=state.tenant_id, owner_user_id=state.student_user_id)
        if evidence:
            workflow_store.sync_from_state(state, source_type="evidence", source_id=evidence["evidence_id"], preset_id=_workflow_preset_id(state.tenant_id))
    try:
        stored = object_storage.put(
            tenant_id=tenant_id, owner_id=owner_user_id or "anonymous", filename=file.filename or "upload",
            content=content, content_type=file.content_type or "",
        )
        storage_meta = storage_registry.record(
            stored=stored, tenant_id=tenant_id, owner_user_id=owner_user_id, session_id=session_id,
            scan_status=security_report.malware_scan,
        )
    except Exception as exc:
        if settings.is_production:
            raise HTTPException(status_code=500, detail=f"文件存储失败: {exc}")
        storage_meta = {"provider": "unavailable", "warning": str(exc)}
    commercial_store.track(tenant_id=tenant_id, user_id=owner_user_id, session_id=session_id, event_name="file_uploaded", properties={"filename": file.filename or "upload", "size_bytes": len(content)})
    return {
        "filename": file.filename, "text": text[:120000], "truncated": len(text) > 120000,
        "evidence": evidence, "storage": storage_meta, "security": security_report.__dict__,
    }


@app.get("/api/files/{object_id}/access")
def create_file_access(object_id: str, request: Request, principal: Principal = Depends(current_principal)):
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    meta = storage_registry.get(object_id, tenant_id=tenant_id)
    if not meta:
        raise HTTPException(status_code=404, detail="file not found")
    _authorize_stored_object(meta, principal)
    ttl = settings.file_signed_url_ttl_seconds
    if meta.get("provider") == "s3" and hasattr(object_storage, "presigned_get_url"):
        return {
            "object_id": object_id, "access_url": object_storage.presigned_get_url(meta["object_key"], expires_seconds=ttl),
            "expires_in": ttl, "delivery": "s3_presigned",
        }
    signed = file_signer.issue(object_id=object_id, tenant_id=meta["tenant_id"], ttl_seconds=ttl)
    url = str(request.base_url).rstrip("/") + f"/api/files/{object_id}/download?token={signed['token']}"
    return {"object_id": object_id, "access_url": url, "expires": signed["expires"], "delivery": "local_signed"}


@app.get("/api/files/{object_id}/download")
def download_signed_file(object_id: str, token: str = Query(...)):
    try:
        payload = file_signer.verify(token, object_id=object_id)
    except UploadSecurityError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    meta = storage_registry.get(object_id, tenant_id=payload["tenant_id"])
    if not meta:
        raise HTTPException(status_code=404, detail="file not found")
    if meta.get("provider") != "local" or not isinstance(object_storage, LocalStorageAdapter):
        raise HTTPException(status_code=400, detail="this object must be accessed through its provider presigned URL")
    try:
        path = object_storage.get_path(meta["object_key"])
    except StorageError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return FileResponse(path, media_type=meta.get("content_type") or "application/octet-stream", filename=meta.get("filename") or object_id)


@app.delete("/api/files/{object_id}")
def delete_stored_file(object_id: str, principal: Principal = Depends(current_principal)):
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    meta = storage_registry.get(object_id, tenant_id=tenant_id)
    if not meta:
        raise HTTPException(status_code=404, detail="file not found")
    _authorize_stored_object(meta, principal)
    try:
        object_storage.delete(meta["object_key"])
        storage_registry.mark_deleted(object_id, tenant_id=tenant_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"file deletion failed: {exc}")
    return {"ok": True, "object_id": object_id}


# ---------------- Workflow / artifacts / evidence ----------------
@app.get("/api/sessions/{session_id}/workflow")
def session_workflow(session_id: str, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal)
    return _workflow_for_state(state)


@app.get("/api/sessions/{session_id}/artifacts")
def session_artifacts(session_id: str, include_content: bool = Query(default=False), principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal)
    return {"artifacts": artifact_store.list_session(session_id, include_content=include_content, tenant_id=state.tenant_id)}


@app.get("/api/artifacts/{artifact_id}")
def read_artifact(artifact_id: str, principal: Principal = Depends(current_principal)):
    try:
        artifact = artifact_store.get(artifact_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="artifact not found")
    state = get_authorized_state(artifact["session_id"], principal)
    return artifact_store.get(artifact_id, tenant_id=state.tenant_id)


@app.get("/api/artifacts/{artifact_id}/versions")
def artifact_versions(artifact_id: str, principal: Principal = Depends(current_principal)):
    try:
        artifact = artifact_store.get(artifact_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="artifact not found")
    state = get_authorized_state(artifact["session_id"], principal)
    return {"versions": artifact_store.list_versions(artifact["artifact_id"],tenant_id=state.tenant_id)}


@app.get("/api/artifacts/{artifact_id}/diff")
def artifact_diff(artifact_id: str, from_version: int = Query(ge=1), to_version: int = Query(ge=1), principal: Principal = Depends(current_principal)):
    try:
        artifact = artifact_store.get(artifact_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="artifact not found")
    state = get_authorized_state(artifact["session_id"],principal)
    try:
        return artifact_store.diff_versions(artifact["artifact_id"],from_version,to_version,tenant_id=state.tenant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="artifact version not found")


@app.post("/api/artifacts/{artifact_id}/restore/{version_id}")
def artifact_restore(artifact_id: str, version_id: str, principal: Principal = Depends(current_principal)):
    try:
        artifact = artifact_store.get(artifact_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="artifact not found")
    state = get_authorized_state(artifact["session_id"],principal,write=True)
    try:
        restored = artifact_store.restore_version(artifact["artifact_id"],version_id,tenant_id=state.tenant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="artifact version not found")
    return {"ok":True,"artifact":restored}


@app.get("/api/sessions/{session_id}/evidence")
def session_evidence(session_id: str, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal)
    return {"items": evidence_store.list_session(session_id, tenant_id=state.tenant_id)}


@app.get("/api/sessions/{session_id}/feedback")
def session_feedback(session_id: str, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal)
    return {"feedback": collaboration_store.list_feedback(session_id, tenant_id=state.tenant_id)}


@app.get("/api/sessions/{session_id}/evidence-graph")
def session_evidence_graph(session_id: str, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal)
    return evidence_graph.session_graph(session_id, tenant_id=state.tenant_id)


@app.post("/api/sessions/{session_id}/evidence-verify")
def verify_session_evidence_claims(session_id: str, req: EvidenceVerificationRequest, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal, write=True)
    claims = evidence_graph.list_claims(session_id, tenant_id=state.tenant_id, claim_ids=req.claim_ids or None)
    evidence_items = evidence_store.list_session(session_id, limit=500, tenant_id=state.tenant_id)
    results = []
    for claim in claims:
        if claim.get("claim_type") != "artifact_claim":
            continue
        verification = evidence_verifier.verify(claim.get("claim_text", ""), evidence_items)
        updated = evidence_graph.update_claim_verification(
            claim["claim_id"], tenant_id=state.tenant_id, status=verification.status,
            confidence=verification.confidence, verified_by=(principal.user_id if principal.authenticated else "system"),
            verifier_type="ai", reason=verification.reason, session_id=session_id,
            risk_level=verification.risk_level, requires_human_review=verification.requires_human_review,
        )
        results.append({
            "claim_id": claim["claim_id"], "claim_text": claim.get("claim_text", ""),
            "verification_status": verification.status, "confidence": round(verification.confidence, 4),
            "best_evidence_id": verification.best_evidence_id, "reason": verification.reason,
            "risk_level": verification.risk_level, "requires_human_review": verification.requires_human_review,
            "candidates": verification.candidates or [], "persisted": updated,
        })
    return {"session_id": session_id, "verified": len(results), "results": results}


@app.get("/api/sessions/{session_id}/claims/{claim_id}/verification-history")
def claim_verification_history(session_id: str, claim_id: str, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal)
    claims = evidence_graph.list_claims(session_id, tenant_id=state.tenant_id, claim_ids=[claim_id])
    if not claims:
        raise HTTPException(status_code=404, detail="claim not found")
    return {"claim": claims[0], "history": evidence_graph.verification_history(claim_id, tenant_id=state.tenant_id)}


@app.post("/api/sessions/{session_id}/claims/{claim_id}/verify")
def manual_claim_verification(session_id: str, claim_id: str, req: ManualClaimVerificationRequest, principal: Principal = Depends(require_roles("advisor", "organization_admin"))):
    state = get_authorized_state(session_id, principal, write=True)
    claims = evidence_graph.list_claims(session_id, tenant_id=state.tenant_id, claim_ids=[claim_id])
    if not claims:
        raise HTTPException(status_code=404, detail="claim not found")
    updated = evidence_graph.update_claim_verification(
        claim_id, tenant_id=state.tenant_id, status=req.status, confidence=req.confidence,
        verified_by=principal.user_id, verifier_type="human", reason=req.reason, session_id=session_id,
        risk_level=str(claims[0].get("risk_level") or "normal"), requires_human_review=False,
    )
    auth_store.audit(tenant_id=state.tenant_id, user_id=principal.user_id, action="claim_verification_override", resource_type="claim", resource_id=claim_id, details={"status": req.status})
    return {"ok": True, "claim": updated, "history": evidence_graph.verification_history(claim_id, tenant_id=state.tenant_id)}


@app.get("/api/artifacts/{artifact_id}/trace")
def artifact_trace(artifact_id: str, principal: Principal = Depends(current_principal)):
    try:
        artifact = artifact_store.get(artifact_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="artifact not found")
    state = get_authorized_state(artifact["session_id"], principal)
    return evidence_graph.artifact_trace(artifact["artifact_id"], tenant_id=state.tenant_id)


@app.post("/api/sessions/{session_id}/workflow/steps/{step_id}/complete")
def complete_workflow_step(session_id: str, step_id: str, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(session_id, principal, write=True)
    try:
        return workflow_store.mark_completed(
            session_id, step_id, tenant_id=state.tenant_id,
            completed_by=(principal.user_id if principal.authenticated else "local-demo"),
            source_type="manual", source_id="api",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="workflow step not found")


# ---------------- AI task center ----------------
@app.get("/api/tasks")
def list_ai_tasks(status: str = Query(default=""), limit: int = Query(default=200, ge=1, le=1000), principal: Principal = Depends(current_principal)):
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    tasks = collaboration_store.list_tasks(tenant_id=tenant_id, status=status or None, limit=limit)
    if principal.authenticated and canonical_role(principal.role) == "participant":
        allowed = {s.session_id for s,_ in store.list(limit=1000,tenant_id=tenant_id,student_user_id=principal.user_id)}
        tasks = [t for t in tasks if t["session_id"] in allowed]
    elif principal.authenticated and canonical_role(principal.role) == "advisor":
        class_ids = auth_store.user_class_ids(principal.user_id,tenant_id,role="teacher")
        allowed = {s.session_id for s,_ in store.list(limit=2000,tenant_id=tenant_id) if s.class_id in class_ids}
        tasks = [t for t in tasks if not t["session_id"] or t["session_id"] in allowed]
    return {"tasks": tasks}


@app.post("/api/tasks")
def create_ai_task(req: AITaskCreateRequest, principal: Principal = Depends(require_roles("teacher","school_admin"))):
    tenant_id = principal.tenant_id if principal.authenticated else req.tenant_id
    if req.session_id:
        get_authorized_state(req.session_id, principal, write=True)
    task = collaboration_store.create_task(
        req.title, req.task_type, session_id=req.session_id, tenant_id=tenant_id,
        priority=req.priority, source="manual", payload=req.payload, owner_user_id=principal.user_id if principal.authenticated else "",
    )
    commercial_store.track(tenant_id=tenant_id, user_id=(principal.user_id if principal.authenticated else ""), session_id=req.session_id, event_name="task_created", properties={"task_type": req.task_type})
    return {"ok": True, "task": task}


@app.patch("/api/tasks/{task_id}")
def update_ai_task(task_id: str, req: AITaskUpdateRequest, principal: Principal = Depends(current_principal)):
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    try:
        task = collaboration_store.get_task(task_id,tenant_id=tenant_id)
        if task.get("session_id"):
            get_authorized_state(task["session_id"],principal,write=True)
        updated = collaboration_store.update_task(task_id,status=req.status,priority=req.priority,tenant_id=tenant_id)
        if req.status == "completed":
            commercial_store.track(tenant_id=tenant_id, user_id=(principal.user_id if principal.authenticated else ""), session_id=task.get("session_id", ""), event_name="task_completed", properties={"task_type": task.get("task_type", "")})
        return {"ok": True, "task": updated}
    except KeyError:
        raise HTTPException(status_code=404, detail="task not found")


# ---------------- Runtime certification ----------------
@app.get("/api/admin/system/runtime-certification")
def runtime_certification_report(principal: Principal = Depends(require_roles("school_admin"))):
    report = load_runtime_certification(settings.runtime_certification_file, settings=settings)
    return {
        "available": Path(settings.runtime_certification_file).is_file(),
        "path": settings.runtime_certification_file,
        "valid": bool(report.get("valid")),
        "reason": report.get("reason", ""),
        "report": report,
    }


@app.post("/api/admin/system/runtime-certification")
async def run_runtime_certification(
    storage_roundtrip: bool = Query(default=False),
    include_llm: bool = Query(default=False),
    profile: str = Query(default="full", pattern="^(full|infrastructure|ai)$"),
    principal: Principal = Depends(require_roles("super_admin")),
):
    certifier = RuntimeCertification(
        settings=settings, embedding_gateway=embedding_gateway, object_storage=object_storage,
        model_store=model_store, llm_gateway=agents.gateway,
    )
    report = await certifier.run(storage_roundtrip=storage_roundtrip, include_llm=include_llm, profile=profile)
    signed = write_certification(report, settings.runtime_certification_file, secret_key=settings.app_secret_key)
    auth_store.audit(
        tenant_id=principal.tenant_id, user_id=principal.user_id, action="runtime_certification",
        resource_type="system", resource_id="runtime", success=bool(signed.get("all_required_pass")),
        details={"storage_roundtrip": storage_roundtrip, "include_llm": include_llm, "profile": profile},
    )
    return signed


@app.get("/api/admin/system/business-certification")
def business_certification_report(principal: Principal = Depends(require_roles("school_admin"))):
    report = load_business_certification(settings.business_certification_file, settings=settings)
    return {
        "available": Path(settings.business_certification_file).is_file(),
        "path": settings.business_certification_file,
        "valid": bool(report.get("valid")),
        "reason": report.get("reason", ""),
        "report": report,
    }


# ---------------- Production readiness diagnostics ----------------
@app.get("/api/admin/system/readiness")
def production_readiness(principal: Principal = Depends(require_roles("school_admin"))):
    providers = [p for p in model_store.list_providers() if p.get("enabled", True)]
    routes = model_store.list_routes()
    blockers: list[str] = []
    warnings: list[str] = []
    if settings.demo_mode:
        blockers.append("DEMO_MODE is enabled; real model execution is disabled")
    if settings.is_production and not settings.auth_required:
        blockers.append("Production authentication is not enforced")
    db_caps = database_capabilities(
        database_url=settings.database_url,
        db_path=settings.db_path,
        repository_backend=settings.repository_backend,
        app_env=settings.app_env,
    )
    blockers.extend(x for x in db_caps.blockers if x not in blockers)
    warnings.extend(x for x in db_caps.warnings if x not in warnings)
    vector_caps = {"postgresql": False, "extension": False, "column": False, "ready": False}
    knowledge_engine = getattr(knowledge_store, "engine", None)
    if knowledge_engine is not None:
        vector_caps = pgvector_capabilities(knowledge_engine)
    if settings.is_production and settings.repository_backend == "postgresql" and not vector_caps.get("ready"):
        blockers.append("PostgreSQL pgvector extension/vector column is not ready; run Alembic migration 0002 and verify the vector extension")
    postgres_cert = load_certification(settings.postgres_certification_file, database_url=settings.database_url) if settings.database_url else {"valid": False, "reason": "DATABASE_URL not configured"}
    if settings.is_production and settings.repository_backend == "postgresql" and not postgres_cert.get("valid"):
        blockers.append("Live PostgreSQL repository certification is missing or stale; run scripts/certify_postgres.py against the target database")
    if settings.repository_backend == "sqlite":
        warnings.append("SQLite is the compatibility runtime. SQLAlchemy repository parity is implemented; use PostgreSQL + Alembic for staging/production after live integration verification")
    if not embedding_gateway.semantic_enabled:
        warnings.append("Semantic embedding provider is not enabled; Hybrid RAG is using local-hash fallback")
    redis_caps = redis_capabilities(settings.redis_url)
    runtime_caps = rate_limiter.capabilities()
    job_caps = background_jobs.capabilities()
    if settings.storage_provider == "local":
        warnings.append("Local file storage is active; use S3-compatible private object storage for production")
    if settings.is_production and not settings.demo_mode:
        if settings.runtime_state_backend != "redis" or not redis_caps.get("ready"):
            blockers.append("Distributed Redis runtime state/rate limiting is not ready")
        if settings.background_job_backend != "redis" or not job_caps.get("ready"):
            blockers.append("Distributed background job queue is not ready")
        if settings.storage_provider != "s3":
            blockers.append("Private S3-compatible object storage is required for non-demo production")
        if not settings.malware_scan_command:
            warnings.append("Malware scanning hook is not configured for uploaded files")
        if not settings.sentry_dsn:
            warnings.append("Sentry-compatible error monitoring is not configured")
    if not providers and not settings.demo_mode:
        blockers.append("No enabled LLM provider is configured")
    if len(routes) < 6 and not settings.demo_mode:
        warnings.append("Not all six Agent routes are configured")
    if settings.is_production and not settings.demo_mode and not settings.pii_redaction_enabled:
        warnings.append("PII_REDACTION_ENABLED is disabled; third-party model data minimization is not enforced")
    if settings.billing_enabled and settings.billing_provider == "mock":
        blockers.append("Real billing is enabled but only the mock/sandbox billing provider is configured")
    if settings.is_production and not settings.demo_mode and settings.email_provider == "console":
        blockers.append("External email delivery is not configured; console outbox cannot be used for production identity lifecycle")
    runtime_cert = load_runtime_certification(settings.runtime_certification_file, settings=settings)
    business_cert = load_business_certification(settings.business_certification_file, settings=settings)
    if settings.is_production and not settings.demo_mode and not runtime_cert.get("valid"):
        blockers.append("Signed full runtime certification is missing, stale, invalid, or incomplete; run scripts/certify_runtime.py against the target environment")
    if settings.is_production and not settings.demo_mode and not business_cert.get("valid"):
        blockers.append("Signed business E2E certification is missing, stale, invalid, or incomplete; run scripts/certify_business_e2e.py against the running API")
    return {
        "ready_for_public_production": not blockers,
        "blockers": blockers,
        "warnings": warnings,
        "runtime": {
            "app_env": settings.app_env, "demo_mode": settings.demo_mode,
            "database_backend": db_caps.backend, "repository_backend": settings.repository_backend,
            "database_url_configured": bool(settings.database_url), "postgres_driver_available": db_caps.postgres_driver_available,
            "schema_bootstrap_mode": settings.schema_bootstrap_mode,
            "embedding_provider": embedding_gateway.config.provider, "semantic_embedding": embedding_gateway.semantic_enabled,
            "embedding_model": embedding_gateway.model_name, "pgvector": vector_caps, "storage_provider": settings.storage_provider,
            "runtime_state": runtime_caps, "redis": redis_caps, "background_jobs": job_caps,
            "upload_security": {"malware_scan_configured": bool(settings.malware_scan_command), "signed_url_ttl_seconds": settings.file_signed_url_ttl_seconds},
            "observability": observability_state,
            "model_governance": {"capability_records": len(model_store.list_model_capabilities()), "evaluation_runs": len(model_store.list_model_evals(principal.tenant_id, limit=500))},
            "privacy": {"pii_redaction_enabled": settings.pii_redaction_enabled, "data_export": True, "delete_request_workflow": True, "controlled_delete_executor_enabled": settings.privacy_delete_executor_enabled, "hard_delete_all_retained_records": False},
            "billing": {"enabled": settings.billing_enabled, "provider": settings.billing_provider, "sandbox": bool(getattr(billing_runtime, "sandbox", False)), "real_provider_verified": False},
            "email": {"provider": settings.email_provider, "external_delivery_configured": settings.email_provider != "console"},
            "runtime_certification": {"available": Path(settings.runtime_certification_file).is_file(), "valid": bool(runtime_cert.get("valid")), "all_required_pass": bool(runtime_cert.get("all_required_pass")), "generated_at": runtime_cert.get("generated_at"), "reason": runtime_cert.get("reason", "")},
            "business_certification": {"available": Path(settings.business_certification_file).is_file(), "valid": bool(business_cert.get("valid")), "all_required_pass": bool(business_cert.get("all_required_pass")), "generated_at": business_cert.get("generated_at"), "reason": business_cert.get("reason", "")},
            "llm_providers": len(providers), "agent_routes": len(routes),
            "postgres_certification": {"valid": bool(postgres_cert.get("valid")), "reason": postgres_cert.get("reason", ""), "certified_at": postgres_cert.get("certified_at")},
        },
    }


@app.get("/api/admin/system/repositories")
def repository_diagnostics(principal: Principal = Depends(require_roles("school_admin"))):
    caps = database_capabilities(
        database_url=settings.database_url,
        db_path=settings.db_path,
        repository_backend=settings.repository_backend,
        app_env=settings.app_env,
    )
    postgres_cert = load_certification(settings.postgres_certification_file, database_url=settings.database_url) if settings.database_url else {"valid": False, "reason": "DATABASE_URL not configured"}
    return {
        "runtime_backend": repositories.backend,
        "requested_backend": settings.repository_backend,
        "database_backend": caps.backend,
        "postgres_driver_available": caps.postgres_driver_available,
        "production_ready": caps.production_ready,
        "blockers": list(caps.blockers),
        "warnings": list(caps.warnings),
        "migration": migration_status(settings.db_path),
        "schema_baseline": "alembic/versions/0001_v10_baseline.py",
        "repository_parity": {"complete": list(CORE_PARITY.complete), "pending": list(CORE_PARITY.pending), "percent": CORE_PARITY.percent, "code_parity_complete": CORE_PARITY.code_parity_complete, "build_environment_live_postgres_verified": CORE_PARITY.live_postgres_verified, "runtime_certification_valid": bool(postgres_cert.get("valid")), "production_cutover_ready": bool(CORE_PARITY.code_parity_complete and postgres_cert.get("valid"))},
        "postgres_certification": postgres_cert,
        "note": "v1.0-beta1 adds business E2E certification, independent-worker verification, cross-tenant attack checks, real presigned-URL HTTP retrieval, SQLite→PostgreSQL migration drill and PostgreSQL backup/restore certification. External services remain NOT VERIFIED until the beta1 staging gate passes against real infrastructure.",
    }


# Tenant-authored workflow/artifact configuration routes.
app.include_router(build_template_admin_router(
    template_registry=template_registry,
    admin_dependency=require_roles("school_admin"),
))


# ---------------- Privacy / data subject rights ----------------
# Route factories keep domain HTTP wiring out of the application composition root.
app.include_router(build_privacy_router(
    current_principal=current_principal,
    require_roles=require_roles,
    auth_store=auth_store,
    session_store=store,
    artifact_store=artifact_store,
    evidence_store=evidence_store,
    evidence_graph=evidence_graph,
    collaboration_store=collaboration_store,
    storage_registry=storage_registry,
    data_lifecycle=data_lifecycle,
    settings=settings,
))

# ---------------- Commercialization / analytics ----------------
app.include_router(build_commercial_router(
    current_principal=current_principal,
    require_roles=require_roles,
    commercial_store=commercial_store,
    billing_runtime=billing_runtime,
    settings=settings,
))

# ---------------- Unified H5 runtime ----------------
# API mode now treats FastAPI persistence as authoritative for all Showcase workspace entities.
app.include_router(build_unified_runtime_router(
    repository=unified_runtime_store,
    current_principal=current_principal,
    canonical_role=canonical_role,
    auth_store=auth_store,
))

# ---------------- Canonical workspace BFF ----------------
# The complete H5 consumes these domain-backed APIs for business entities.
# Generic Unified Runtime is reserved for transient/UI state and compatibility.
app.include_router(build_workspace_router(
    sessions=store,
    identity=auth_store,
    evidence=evidence_store,
    evidence_graph=evidence_graph,
    artifacts=artifact_store,
    collaboration=collaboration_store,
    knowledge=knowledge_store,
    jobs=job_store,
    agents=agents,
    current_principal=current_principal,
    canonical_role=canonical_role,
))

app.include_router(build_domain_intelligence_router(
    sessions=store,
    identity=auth_store,
    evidence=evidence_store,
    artifacts=artifact_store,
    jobs=job_store,
    domain_service=domain_intelligence_service,
    domain_store=domain_intelligence_store,
    current_principal=current_principal,
    canonical_role=canonical_role,
))

# ---------------- Knowledge base / data ingestion APIs ----------------
@app.post("/api/admin/knowledge/ingest")
async def ingest_knowledge(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    scope: str = Form(default="global"),
    tags: str = Form(default=""),
    category: str = Form(default="other"),
    authority: str = Form(default="internal"),
    effective_year: str = Form(default=""),
    priority: int = Form(default=50),
    x_admin_token: str | None = Header(default=None),
    principal: Principal = Depends(require_roles("school_admin")),
):
    _require_entitlement(principal.tenant_id, "knowledge_base")
    content = await file.read()
    _validate_upload_security(file, content)
    try:
        text = parse_uploaded_file(file.filename or "upload", content)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not text.strip():
        raise HTTPException(status_code=400, detail="文件未解析出可用文本")
    tag_list = [x.strip() for x in tags.split(",") if x.strip()]
    result = knowledge_store.ingest(
        title=title.strip() or Path(file.filename or "知识文档").stem,
        filename=file.filename or "upload",
        mime_type=file.content_type or "",
        text=text,
        scope=scope.strip() or "global",
        tags=tag_list,
        category=category.strip() or "other",
        authority=authority.strip() or "internal",
        effective_year=effective_year.strip(),
        priority=max(0, min(100, int(priority))),
        tenant_id=("global" if principal.is_super_admin else principal.tenant_id),
    )
    return {"ok": True, "source": result}


@app.post("/api/admin/knowledge/text")
def ingest_knowledge_text(req: KnowledgeTextIngest, x_admin_token: str | None = Header(default=None), principal: Principal = Depends(require_roles("school_admin"))):
    _require_entitlement(principal.tenant_id, "knowledge_base")
    result = knowledge_store.ingest(
        title=req.title,
        filename="manual-text",
        mime_type="text/plain",
        text=req.text,
        scope=req.scope,
        tags=req.tags,
        category=req.category,
        authority=req.authority,
        effective_year=req.effective_year,
        priority=req.priority,
        tenant_id=("global" if principal.is_super_admin else principal.tenant_id),
    )
    return {"ok": True, "source": result}


@app.get("/api/admin/knowledge/sources")
def list_knowledge_sources(x_admin_token: str | None = Header(default=None), principal: Principal = Depends(require_roles("school_admin"))):
    _require_entitlement(principal.tenant_id, "knowledge_base")
    sources = knowledge_store.list_sources(None if principal.is_super_admin else principal.tenant_id)
    return {
        "sources": sources,
        "stats": {
            "sources": len(sources),
            "active_sources": sum(1 for s in sources if s["active"]),
            "chunks": sum(int(s["chunk_count"]) for s in sources if s["active"]),
            "characters": sum(int(s["char_count"]) for s in sources if s["active"]),
        },
    }


@app.post("/api/admin/knowledge/search")
def search_knowledge(req: KnowledgeSearchRequest, x_admin_token: str | None = Header(default=None), principal: Principal = Depends(require_roles("school_admin"))):
    _require_entitlement(principal.tenant_id, "knowledge_base")
    result = knowledge_store.search_detailed(
        req.query, scope=req.scope, top_k=req.top_k,
        tenant_id=("global" if principal.is_super_admin else principal.tenant_id),
        effective_year=req.effective_year,
    )
    return {
        "hits": [{
            "source_id": h.source_id, "title": h.source_title, "chunk_id": h.chunk_id,
            "chunk_index": h.chunk_index, "score": h.score, "content": h.content,
        } for h in result["hits"]],
        "retrieval": result.get("retrieval", {}),
        "breakdown": result.get("breakdown", []),
    }


@app.post("/api/admin/knowledge/evaluate")
def evaluate_knowledge_retrieval(req: RAGEvaluationRequest, principal: Principal = Depends(require_roles("school_admin"))):
    _require_entitlement(principal.tenant_id, "knowledge_base")
    tenant_id = "global" if principal.is_super_admin else principal.tenant_id
    cases = [RAGEvalCase(**case.model_dump()) for case in req.cases]
    return evaluate_rag(knowledge_store, cases, tenant_id=tenant_id, k=10)


@app.post("/api/admin/knowledge/reindex")
def reindex_knowledge(principal: Principal = Depends(require_roles("school_admin"))):
    _require_entitlement(principal.tenant_id, "knowledge_base")
    # Synchronous compatibility endpoint. Large production indexes should use /reindex-async.
    return {"ok": True, **knowledge_store.rebuild_hybrid_index(only_missing=False, tenant_id=(None if principal.is_super_admin else principal.tenant_id))}


@app.post("/api/admin/knowledge/reindex-async")
def reindex_knowledge_async(only_missing: bool = Query(default=True), principal: Principal = Depends(require_roles("school_admin"))):
    _require_entitlement(principal.tenant_id, "knowledge_base")
    job = background_jobs.enqueue(
        name="knowledge_reindex", payload={"only_missing": only_missing, "tenant_id": (None if principal.is_super_admin else principal.tenant_id)}, tenant_id=principal.tenant_id, user_id=principal.user_id,
        idempotency_key=f"knowledge_reindex:{'missing' if only_missing else 'full'}", timeout_seconds=1800,
    )
    return {"ok": True, "job": jsonable_encoder(job)}


@app.get("/api/runtime/jobs/{job_id}")
def get_runtime_job(job_id: str, principal: Principal = Depends(current_principal)):
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    job = background_jobs.get(job_id, tenant_id=tenant_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if canonical_role(principal.role) == "participant" and job.user_id and job.user_id != principal.user_id:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job": jsonable_encoder(job)}


@app.post("/api/runtime/jobs/{job_id}/cancel")
def cancel_runtime_job(job_id: str, principal: Principal = Depends(current_principal)):
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    job = background_jobs.get(job_id, tenant_id=tenant_id)
    if not job or (canonical_role(principal.role) == "participant" and job.user_id and job.user_id != principal.user_id):
        raise HTTPException(status_code=404, detail="job not found")
    return {"ok": background_jobs.cancel(job_id, tenant_id=tenant_id), "job_id": job_id}


@app.post("/api/runtime/jobs/{job_id}/retry")
def retry_runtime_job(job_id: str, principal: Principal = Depends(current_principal)):
    tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
    job = background_jobs.get(job_id, tenant_id=tenant_id)
    if not job or (canonical_role(principal.role) == "participant" and job.user_id and job.user_id != principal.user_id):
        raise HTTPException(status_code=404, detail="job not found")
    retried = background_jobs.retry(job_id, tenant_id=tenant_id)
    if not retried:
        raise HTTPException(status_code=409, detail="job is not retryable")
    return {"ok": True, "job": jsonable_encoder(retried)}


@app.patch("/api/admin/knowledge/sources/{source_id}")
def update_knowledge_source(source_id: str, req: KnowledgeSourceUpdate, x_admin_token: str | None = Header(default=None), principal: Principal = Depends(require_roles("school_admin"))):
    _require_entitlement(principal.tenant_id, "knowledge_base")
    knowledge_store.update_source(source_id, title=req.title, scope=req.scope, tags=req.tags, active=req.active, category=req.category, authority=req.authority, effective_year=req.effective_year, priority=req.priority, tenant_id=(None if principal.is_super_admin else principal.tenant_id))
    return {"ok": True}


@app.delete("/api/admin/knowledge/sources/{source_id}")
def delete_knowledge_source(source_id: str, x_admin_token: str | None = Header(default=None), principal: Principal = Depends(require_roles("school_admin"))):
    _require_entitlement(principal.tenant_id, "knowledge_base")
    knowledge_store.delete_source(source_id, tenant_id=(None if principal.is_super_admin else principal.tenant_id))
    return {"ok": True}


# ---------------- Structured job data ----------------
@app.get("/api/admin/jobs")
def search_jobs(
    q: str = Query(default=""), city: str = Query(default=""), industry: str = Query(default=""),
    limit: int = Query(default=30, ge=1, le=500), x_admin_token: str | None = Header(default=None),
    principal: Principal = Depends(require_roles("school_admin")),
):
    tenant_id = "global" if principal.is_super_admin else principal.tenant_id
    return {"stats": job_store.stats(tenant_id=tenant_id), "jobs": job_store.search(q, city=city, industry=industry, limit=limit, tenant_id=tenant_id)}


@app.post("/api/admin/jobs/ingest-csv")
async def ingest_jobs_csv(file: UploadFile = File(...), x_admin_token: str | None = Header(default=None), principal: Principal = Depends(require_roles("school_admin"))):
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="岗位结构化导入仅支持 CSV")
    content = await file.read()
    _validate_upload_security(file, content)
    return {"ok": True, **job_store.ingest_csv(content, source=file.filename or "csv", tenant_id=("global" if principal.is_super_admin else principal.tenant_id))}


@app.delete("/api/admin/jobs/{job_id}")
def delete_job(job_id: str, principal: Principal = Depends(require_roles("organization_admin"))):
    tenant_id = "global" if principal.is_super_admin else principal.tenant_id
    if tenant_id == "global" and not principal.is_super_admin:
        raise HTTPException(status_code=403, detail="global job deletion requires super admin")
    deleted = job_store.delete_job(job_id, tenant_id=tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="job not found or not tenant-owned")
    return {"ok": True, "deleted": True, "job_id": job_id}


@app.get("/api/admin/jobs/{job_id}/requirements")
def admin_job_requirements(job_id: str, principal: Principal = Depends(require_roles("organization_admin"))):
    tenant_id = "global" if principal.is_super_admin else principal.tenant_id
    try:
        requirements = job_intelligence.ensure_requirements(job_id, tenant_id=tenant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job_id": job_id, "requirements": requirements}


@app.post("/api/jobs/{job_id}/match")
def match_job(job_id: str, req: JobMatchRequest, principal: Principal = Depends(current_principal)):
    state = get_authorized_state(req.session_id, principal)
    try:
        return job_intelligence.match(
            job_id=job_id, tenant_id=state.tenant_id, profile=state.profile,
            evidence_items=evidence_store.list_session(state.session_id, limit=500, tenant_id=state.tenant_id),
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="job not found")


# ---------------- Teacher dashboard ----------------
def _risk_flags(state: SessionState) -> list[str]:
    flags: list[str] = []
    domain = _domain_for_tenant(state.tenant_id)
    if not state.profile.target_job:
        flags.append("职业目标未明确")
    if domain.enable_competition_template and state.track == "待确认":
        flags.append("赛道待确认")
    if state.draft and not state.review:
        flags.append("成果待评审")
    if state.review and state.review.total_score < 70:
        flags.append("评分低于70")
    if state.review and state.review.fatal_issues:
        flags.append("存在致命问题")
    return flags


def _sync_risk_tasks(state: SessionState) -> None:
    mapping = {
        "职业目标未明确": ("明确职业目标", "career_goal", "medium"),
        "赛道待确认": ("确认当前业务路径", "confirm_track", "medium"),
        "成果待评审": ("完成成果严格评审", "review_draft", "normal"),
        "评分低于70": ("修订低分作品", "revise_low_score", "high"),
        "存在致命问题": ("处理评审致命问题", "fatal_review_issue", "high"),
    }
    for flag in _risk_flags(state):
        title, task_type, priority = mapping[flag]
        collaboration_store.ensure_task(
            title, task_type, session_id=state.session_id, tenant_id=state.tenant_id,
            priority=priority, source="risk_engine", payload={"risk": flag},
        )


@app.get("/api/advisor/dashboard")
@app.get("/api/teacher/dashboard")
def teacher_dashboard(
    q: str = Query(default=""),
    stage: str = Query(default="all"),
    tenant_id: str = Query(default=""),
    class_id: str = Query(default=""),
    limit: int = Query(default=200, ge=1, le=1000),
    principal: Principal = Depends(require_roles("teacher", "school_admin")),
):
    target_tenant = _tenant_for(principal, tenant_id or None)
    effective_class = class_id or None
    if principal.authenticated and canonical_role(principal.role) == "advisor" and not principal.is_super_admin:
        allowed_classes = auth_store.user_class_ids(principal.user_id, target_tenant, role="teacher")
        if class_id and class_id not in allowed_classes:
            raise HTTPException(status_code=403, detail="class access denied")
        rows = store.list(limit=limit, tenant_id=target_tenant, class_id=effective_class)
        rows = [(state, ts) for state, ts in rows if state.class_id in allowed_classes]
    else:
        rows = store.list(limit=limit, tenant_id=target_tenant, class_id=effective_class)

    all_states = [s for s, _ in rows]
    scores = [s.review.total_score for s in all_states if s.review]
    stats = {
        "total_students": len(all_states),
        "profiled": sum(1 for s in all_states if bool(s.profile.evidence_text.strip())),
        "track_confirmed": sum(1 for s in all_states if s.track != "待确认"),
        "drafted": sum(1 for s in all_states if bool(s.draft.strip())),
        "reviewed": sum(1 for s in all_states if s.review is not None),
        "revised": sum(1 for s in all_states if bool(s.revised_draft.strip())),
        "average_score": round(sum(scores) / len(scores), 1) if scores else None,
        "needs_attention": sum(1 for s in all_states if _risk_flags(s)),
    }
    sessions = []
    qn = q.strip().lower()
    for state, updated_at in rows:
        _sync_risk_tasks(state)
        if stage != "all" and state.stage != stage:
            continue
        hay = " ".join([state.profile.name, state.profile.school, state.profile.major, state.profile.target_job, state.session_id]).lower()
        if qn and qn not in hay:
            continue
        sessions.append({
            "session_id": state.session_id,
            "name": state.profile.name or "未命名学生",
            "school": state.profile.school,
            "major": state.profile.major,
            "grade": state.profile.grade,
            "target_job": state.profile.target_job,
            "track": state.track,
            "stage": state.stage,
            "stage_label": STAGE_LABELS.get(state.stage, state.stage),
            "progress": _workflow_for_state(state)["progress"],
            "workflow": _workflow_for_state(state),
            "score": state.review.total_score if state.review else None,
            "risk_flags": _risk_flags(state),
            "updated_at": updated_at,
            "message_count": len(state.messages),
        })
    allowed_session_ids = {s.session_id for s, _ in rows}
    open_tasks = [
        t for t in collaboration_store.list_tasks(tenant_id=target_tenant, status="todo", limit=500)
        if not t["session_id"] or t["session_id"] in allowed_session_ids
    ]
    stats["open_ai_tasks"] = len(open_tasks)
    return {"stats": stats, "sessions": sessions, "tasks": open_tasks[:20], "tenant_id": target_tenant}


@app.get("/api/advisor/sessions/{session_id}")
@app.get("/api/teacher/sessions/{session_id}")
def teacher_session_detail(session_id: str, principal: Principal = Depends(require_roles("teacher", "school_admin"))):
    state = get_authorized_state(session_id, principal)
    _sync_risk_tasks(state)
    return {
        "state": state,
        "risk_flags": _risk_flags(state),
        "workflow": _workflow_for_state(state),
        "artifacts": artifact_store.list_session(session_id, tenant_id=state.tenant_id),
        "evidence": evidence_store.list_session(session_id, tenant_id=state.tenant_id),
        "feedback": collaboration_store.list_feedback(session_id, tenant_id=state.tenant_id),
        "tasks": collaboration_store.list_tasks(state.tenant_id, limit=200, session_id=session_id),
        "evidence_audit": audit_evidence(state.revised_draft or state.draft, state.profile.evidence_text).model_dump() if (state.revised_draft or state.draft) else None,
    }


@app.put("/api/advisor/sessions/{session_id}/note")
@app.put("/api/teacher/sessions/{session_id}/note")
def teacher_note(session_id: str, req: TeacherNoteRequest, principal: Principal = Depends(require_roles("teacher", "school_admin"))):
    state = get_authorized_state(session_id, principal, write=True)
    state.teacher_note = req.note.strip()
    store.save(state)
    return {"ok": True, "teacher_note": state.teacher_note}


@app.post("/api/advisor/sessions/{session_id}/feedback")
@app.post("/api/teacher/sessions/{session_id}/feedback")
def create_teacher_feedback(session_id: str, req: TeacherFeedbackRequest, principal: Principal = Depends(require_roles("teacher", "school_admin"))):
    state = get_authorized_state(session_id, principal, write=True)
    teacher_name = principal.display_name if principal.authenticated else req.teacher_name
    feedback = collaboration_store.add_feedback(
        session_id, req.content, teacher_name=teacher_name, priority=req.priority,
        tenant_id=state.tenant_id, teacher_user_id=(principal.user_id if principal.authenticated else ""),
    )
    # Teacher guidance is intentionally NOT student evidence. It remains a separate collaboration record.
    task = collaboration_store.ensure_task(
        "处理教师反馈", "teacher_feedback", session_id=session_id, tenant_id=state.tenant_id,
        priority=req.priority, source="teacher", payload={"feedback_id": feedback["feedback_id"]},
        owner_user_id=state.student_user_id,
    )
    current_artifact = artifact_store.latest(session_id, tenant_id=state.tenant_id)
    trace = evidence_graph.record_feedback(
        tenant_id=state.tenant_id, session_id=session_id, feedback_id=feedback["feedback_id"], content=req.content,
        artifact_id=(current_artifact or {}).get("artifact_id", ""), version_id=(current_artifact or {}).get("version_id", ""),
    )
    commercial_store.track(tenant_id=state.tenant_id, user_id=(principal.user_id if principal.authenticated else ""), session_id=session_id, event_name="advisor_feedback_created", properties={"priority": req.priority})
    return {"ok": True, "feedback": feedback, "task": task, "trace": trace}


@app.patch("/api/advisor/feedback/{feedback_id}/resolve")
@app.patch("/api/teacher/feedback/{feedback_id}/resolve")
def resolve_teacher_feedback(feedback_id: str, principal: Principal = Depends(require_roles("teacher", "school_admin"))):
    try:
        feedback = collaboration_store.get_feedback(feedback_id, tenant_id=(None if principal.is_super_admin else principal.tenant_id))
    except KeyError:
        raise HTTPException(status_code=404, detail="feedback not found")
    state = get_authorized_state(feedback["session_id"], principal, write=True)
    collaboration_store.resolve_feedback(feedback_id, tenant_id=state.tenant_id)
    collaboration_store.complete_matching(feedback["session_id"], "teacher_feedback", tenant_id=state.tenant_id)
    return {"ok": True}


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _page_guard(request: Request, allowed_roles: set[str]):
    if not settings.auth_required:
        return None
    principal = auth_store.resolve_session(request.cookies.get(AUTH_COOKIE))
    if not principal:
        return RedirectResponse(url=f"/login?next={request.url.path}", status_code=302)
    if not principal.is_super_admin and canonical_role(principal.role) not in {canonical_role(r) for r in allowed_roles}:
        return RedirectResponse(url="/login?error=role", status_code=302)
    return None


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)


@app.get("/login")
def login_page():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/participant")
@app.get("/student")
def student_page(request: Request):
    denied = _page_guard(request, {"student"})
    return denied or FileResponse(STATIC_DIR / "student.html")


@app.get("/advisor")
@app.get("/teacher")
def teacher_page(request: Request):
    denied = _page_guard(request, {"teacher", "school_admin"})
    return denied or FileResponse(STATIC_DIR / "teacher.html")


@app.get("/admin")
def admin_page(request: Request):
    denied = _page_guard(request, {"school_admin"})
    return denied or FileResponse(STATIC_DIR / "admin.html")


@app.get("/showcase")
def showcase_page():
    return FileResponse(STATIC_DIR / "showcase.html")


# Model administration is registered after all legacy route declarations so
# the final canonical API alias pass observes the complete route surface.
app.include_router(build_model_admin_router(
    settings=settings,
    model_store=model_store,
    agents=agents,
    require_roles=require_roles,
    require_admin_legacy=_require_admin_legacy,
))

# Register canonical aliases only after the complete compatibility surface is known.
register_v1_compatibility_aliases(app)
