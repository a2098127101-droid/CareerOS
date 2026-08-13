from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException

from ..spatial_telemetry import SpatialRuntimeTelemetryService, SpatialTelemetryError


def build_spatial_runtime_router(
    *,
    service: SpatialRuntimeTelemetryService,
    current_principal: Callable,
    canonical_role: Callable,
) -> APIRouter:
    router = APIRouter(prefix="/api/spatial-runtime/v1", tags=["spatial-runtime"])

    def authenticated(principal) -> None:
        if not principal.authenticated:
            raise HTTPException(status_code=401, detail="authentication required")

    @router.get("/telemetry/contract")
    def telemetry_contract(principal=Depends(current_principal)):
        authenticated(principal)
        return service.contract()

    @router.post("/telemetry")
    def ingest_telemetry(payload: dict[str, Any], principal=Depends(current_principal)):
        authenticated(principal)
        if canonical_role(principal.role) != "participant":
            raise HTTPException(status_code=403, detail="participant account required")
        try:
            return service.ingest(tenant_id=principal.tenant_id, payload=payload)
        except SpatialTelemetryError as exc:
            raise HTTPException(status_code=422, detail={"code": "invalid_spatial_telemetry", "message": str(exc)})

    @router.get("/telemetry/summary")
    def telemetry_summary(principal=Depends(current_principal)):
        authenticated(principal)
        role = canonical_role(principal.role)
        if not getattr(principal, "is_super_admin", False) and role not in {"advisor", "organization_admin"}:
            raise HTTPException(status_code=403, detail="advisor or organization administrator required")
        return service.summary(tenant_id=principal.tenant_id)

    return router
