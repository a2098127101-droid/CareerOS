from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from ..auth_store import Principal
from ..model_evaluation import run_model_evaluation
from ..models import (
    ModelCapabilityUpsert,
    ModelEvaluationRequest,
    ModelRecommendationRequest,
    ProviderPlaygroundRequest,
    ProviderTestRequest,
    ProviderUpsert,
    RouteUpsert,
)
from ..network_security import (
    OutboundURLSecurityError,
    validate_nonsecret_metadata,
    validate_outbound_url,
)


def build_model_admin_router(
    *,
    settings: Any,
    model_store: Any,
    agents: Any,
    require_roles: Callable[..., Any],
    require_admin_legacy: Callable[[str | None, Principal], None],
) -> APIRouter:
    """Model/provider administration routes.

    Dependencies are injected to preserve the existing stores and API contracts
    while keeping application composition out of this router module.
    """

    router = APIRouter(prefix="/api/admin", tags=["model-admin"])
    super_admin = require_roles("super_admin")

    @router.get("/models/overview")
    def model_overview(
        x_admin_token: str | None = Header(default=None),
        principal: Principal = Depends(super_admin),
    ):
        require_admin_legacy(x_admin_token, principal)
        return {
            "demo_mode": settings.demo_mode,
            "providers": model_store.list_providers(),
            "routes": model_store.list_routes(),
            "capabilities": model_store.list_model_capabilities(),
            "tasks": agents.task_status(),
            "usage": model_store.usage_summary(limit=25),
            "warning": (
                "生产环境必须设置 APP_SECRET_KEY 与 ADMIN_TOKEN。"
                if settings.app_secret_key == "change-me-in-production" or not settings.admin_token
                else None
            ),
        }

    @router.post("/providers")
    def upsert_provider(
        req: ProviderUpsert,
        x_admin_token: str | None = Header(default=None),
        principal: Principal = Depends(super_admin),
    ):
        require_admin_legacy(x_admin_token, principal)
        try:
            validate_outbound_url(req.base_url, allow_private_network=req.allow_private_network)
            if req.oauth_token_url:
                validate_outbound_url(req.oauth_token_url, allow_private_network=req.allow_private_network)
            validate_nonsecret_metadata(req.extra_headers, req.query_params)
        except OutboundURLSecurityError as exc:
            raise HTTPException(
                status_code=400,
                detail={"code": "unsafe_provider_configuration", "message": str(exc)},
            ) from exc
        model_store.upsert_provider(req)
        return {"ok": True, "providers": model_store.list_providers()}

    @router.delete("/providers/{provider_id}")
    def delete_provider(
        provider_id: str,
        x_admin_token: str | None = Header(default=None),
        principal: Principal = Depends(super_admin),
    ):
        require_admin_legacy(x_admin_token, principal)
        model_store.delete_provider(provider_id)
        return {"ok": True}

    @router.post("/providers/test")
    async def test_provider(
        req: ProviderTestRequest,
        x_admin_token: str | None = Header(default=None),
        principal: Principal = Depends(super_admin),
    ):
        require_admin_legacy(x_admin_token, principal)
        try:
            return await agents.gateway.test_provider(req.provider_id, req.model)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/providers/{provider_id}/models")
    async def discover_provider_models(
        provider_id: str,
        x_admin_token: str | None = Header(default=None),
        principal: Principal = Depends(super_admin),
    ):
        require_admin_legacy(x_admin_token, principal)
        try:
            return await agents.gateway.discover_models(provider_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/providers/playground")
    async def provider_playground(
        req: ProviderPlaygroundRequest,
        x_admin_token: str | None = Header(default=None),
        principal: Principal = Depends(super_admin),
    ):
        require_admin_legacy(x_admin_token, principal)
        try:
            return await agents.gateway.invoke_provider(
                req.provider_id,
                model=req.model,
                system=req.system,
                user=req.user,
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                tenant_id=principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put("/routes/{task}")
    def upsert_route(
        task: str,
        req: RouteUpsert,
        x_admin_token: str | None = Header(default=None),
        principal: Principal = Depends(super_admin),
    ):
        require_admin_legacy(x_admin_token, principal)
        if task != req.task:
            raise HTTPException(status_code=400, detail="URL task 与请求体 task 不一致")
        if req.provider_id != "auto" and not model_store.get_provider(req.provider_id):
            raise HTTPException(status_code=400, detail="主 Provider 不存在")
        if req.fallback_provider_id and not model_store.get_provider(req.fallback_provider_id):
            raise HTTPException(status_code=400, detail="Fallback Provider 不存在")
        model_store.upsert_route(req)
        return {"ok": True, "routes": model_store.list_routes(), "tasks": agents.task_status()}

    @router.put("/models/capabilities")
    def upsert_model_capability(
        req: ModelCapabilityUpsert,
        principal: Principal = Depends(super_admin),
    ):
        if not model_store.get_provider(req.provider_id):
            raise HTTPException(status_code=400, detail="provider not found")
        return {"ok": True, "capability": model_store.upsert_model_capability(req)}

    @router.get("/models/capabilities")
    def list_model_capabilities(
        provider_id: str = Query(default=""),
        principal: Principal = Depends(super_admin),
    ):
        return {"models": model_store.list_model_capabilities(provider_id or None)}

    @router.post("/models/recommend")
    def recommend_models(
        req: ModelRecommendationRequest,
        principal: Principal = Depends(super_admin),
    ):
        required = req.required_capabilities
        if req.task and not required:
            return {"candidates": agents.gateway.recommend_models_for_task(req.task), "mode": "task-default"}
        return {
            "candidates": model_store.recommend_models(
                required_capabilities=required,
                min_context_window=req.min_context_window,
                max_input_cost_per_million=req.max_input_cost_per_million,
                max_output_cost_per_million=req.max_output_cost_per_million,
                prefer_latency=req.prefer_latency,
            ),
            "mode": "explicit",
        }

    @router.post("/models/evaluate")
    async def evaluate_model(
        req: ModelEvaluationRequest,
        principal: Principal = Depends(super_admin),
    ):
        try:
            result = await run_model_evaluation(
                gateway=agents.gateway,
                store=model_store,
                tenant_id=principal.tenant_id,
                provider_id=req.provider_id,
                model=req.model,
                task=req.task,
                cases=[item.model_dump() for item in req.cases],
            )
            return {
                "eval_id": result.eval_id,
                "metrics": result.metrics,
                "cases": result.cases,
                "live_api_test": True,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/models/evaluations")
    def list_model_evaluations(
        limit: int = Query(default=50, ge=1, le=500),
        principal: Principal = Depends(super_admin),
    ):
        return {"evaluations": model_store.list_model_evals(principal.tenant_id, limit=limit)}

    @router.get("/models/usage")
    def model_usage(
        limit: int = Query(default=100, ge=1, le=1000),
        x_admin_token: str | None = Header(default=None),
        principal: Principal = Depends(super_admin),
    ):
        require_admin_legacy(x_admin_token, principal)
        return model_store.usage_summary(limit=limit)

    return router
