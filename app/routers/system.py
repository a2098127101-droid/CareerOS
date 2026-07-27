from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..business_certification import load_business_certification
from ..migrations import migration_status
from ..runtime_certification import load_runtime_certification
from ..runtime_state import redis_capabilities


def build_system_router(
    *,
    settings,
    agents,
    knowledge_store,
    job_store,
    embedding_gateway,
    rate_limiter,
    background_jobs,
    observability_state,
    repositories,
    product_profile,
) -> APIRouter:
    router = APIRouter(tags=["System"])

    @router.get("/api/health")
    def health():
        tasks = agents.task_status()
        enabled_count = sum(1 for item in tasks.values() if item["enabled"])
        mode = "demo" if settings.demo_mode or enabled_count == 0 else (
            "llm" if enabled_count == len(tasks) else "hybrid"
        )
        sources = knowledge_store.list_sources()
        return {
            "ok": True,
            "version": "1.5.1-release-hardening",
            "mode": mode,
            "product": {
                "name": settings.product_name,
                "preset": product_profile.profile_id,
                "subtitle": product_profile.product_subtitle,
                "competition_template_enabled": product_profile.enable_competition_template,
            },
            "tasks": tasks,
            "knowledge": {
                "sources": len(sources),
                "chunks": sum(int(item["chunk_count"]) for item in sources if item["active"]),
            },
            "jobs": job_store.stats(),
            "retrieval": {
                "embedding_model": embedding_gateway.model_name,
                "semantic_embedding": embedding_gateway.semantic_enabled,
            },
            "storage": {"provider": settings.storage_provider},
            "runtime_state": rate_limiter.capabilities(),
            "background_jobs": background_jobs.capabilities(),
            "observability": observability_state,
            "repository": {
                "runtime": repositories.backend,
                "requested": settings.repository_backend,
                "database_url_configured": bool(settings.database_url),
            },
            "migrations": migration_status(settings.db_path),
            "auth": {"required": settings.auth_required, "environment": settings.app_env},
            "security": {
                "admin_token_configured": bool(settings.admin_token),
                "custom_secret_configured": settings.app_secret_key != "change-me-in-production",
            },
        }

    @router.get("/live")
    @router.get("/api/live")
    def live_probe():
        return {
            "ok": True,
            "service": settings.otel_service_name,
            "version": "1.5.1-release-hardening",
        }

    @router.get("/ready")
    @router.get("/api/ready")
    def ready_probe():
        redis_caps = redis_capabilities(settings.redis_url)
        blockers = []
        runtime_cert = load_runtime_certification(
            settings.runtime_certification_file,
            settings=settings,
        )
        business_cert = load_business_certification(
            settings.business_certification_file,
            settings=settings,
        )
        if settings.is_production and not settings.demo_mode:
            if settings.runtime_state_backend != "redis" or not redis_caps.get("ready"):
                blockers.append("distributed Redis runtime state is not ready")
            if settings.background_job_backend != "redis":
                blockers.append("distributed background job backend is not enabled")
            if settings.storage_provider != "s3":
                blockers.append("private S3-compatible object storage is not enabled")
            if not runtime_cert.get("valid"):
                blockers.append(
                    "signed live runtime certification is missing, stale, invalid, or incomplete"
                )
            if not business_cert.get("valid"):
                blockers.append(
                    "signed business E2E certification is missing, stale, invalid, or incomplete"
                )
        return JSONResponse(
            {
                "ready": not blockers,
                "blockers": blockers,
                "runtime_state": rate_limiter.capabilities(),
                "redis": redis_caps,
                "background_jobs": background_jobs.capabilities(),
                "storage_provider": settings.storage_provider,
                "runtime_certification": {
                    "valid": bool(runtime_cert.get("valid")),
                    "reason": runtime_cert.get("reason", ""),
                    "generated_at": runtime_cert.get("generated_at"),
                },
                "business_certification": {
                    "valid": bool(business_cert.get("valid")),
                    "reason": business_cert.get("reason", ""),
                    "generated_at": business_cert.get("generated_at"),
                },
            },
            status_code=200 if not blockers else 503,
        )

    return router
