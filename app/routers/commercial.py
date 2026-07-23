from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..billing import BillingError
from ..models import AnalyticsEventRequest, BillingCheckoutRequest, SubscriptionUpdateRequest


def build_commercial_router(*, current_principal, require_roles, commercial_store, billing_runtime, settings) -> APIRouter:
    router = APIRouter(tags=["commercial"])

    @router.get("/api/admin/commercial/overview")
    def commercial_overview(principal=Depends(require_roles("school_admin"))):
        target_tenant = principal.tenant_id
        return {
            "subscription": commercial_store.subscription(target_tenant),
            "plans": commercial_store.list_plans() if principal.is_super_admin else [],
            "analytics": commercial_store.analytics_summary(target_tenant),
            "usage": commercial_store.usage_window(target_tenant),
            "billing": {"enabled": settings.billing_enabled, "provider": settings.billing_provider,
                        "sandbox": bool(getattr(billing_runtime, "sandbox", False)),
                        "status": "sandbox/mock foundation" if getattr(billing_runtime, "sandbox", False) else "configured"},
        }

    @router.put("/api/admin/commercial/subscription/{tenant_id}")
    def update_subscription(tenant_id: str, req: SubscriptionUpdateRequest, principal=Depends(require_roles("super_admin"))):
        commercial_store.set_plan(tenant_id, req.plan_id)
        return commercial_store.subscription(tenant_id)

    @router.post("/api/admin/billing/checkout")
    def billing_checkout(req: BillingCheckoutRequest, principal=Depends(require_roles("school_admin"))):
        if req.plan_id not in {str(p.get("plan_id")) for p in commercial_store.list_plans()}:
            raise HTTPException(status_code=400, detail="unknown plan")
        order = commercial_store.create_billing_order(
            tenant_id=principal.tenant_id, plan_id=req.plan_id, provider=settings.billing_provider,
            metadata={"requested_by": principal.user_id},
        )
        checkout = billing_runtime.create_checkout(
            tenant_id=principal.tenant_id, plan_id=req.plan_id,
            success_url=req.success_url, cancel_url=req.cancel_url,
        )
        return {"order": order, "checkout": checkout,
                "real_payment_created": False if getattr(billing_runtime, "sandbox", False) else None}

    @router.post("/api/billing/webhooks/{provider_id}")
    async def billing_webhook(provider_id: str, request: Request,
                              x_careeros_billing_signature: str = Header(default="", alias="X-CareerOS-Billing-Signature")):
        if provider_id != settings.billing_provider:
            raise HTTPException(status_code=404, detail="billing provider not configured")
        body = await request.body()
        try:
            event = billing_runtime.verify_webhook(body=body, signature=x_careeros_billing_signature)
        except BillingError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        record, duplicate = commercial_store.record_billing_event(
            provider=provider_id, event_key=event.event_key, event_type=event.event_type,
            tenant_id=event.tenant_id, raw_payload=body,
        )
        if duplicate:
            return {"ok": True, "duplicate": True, "event_id": record.get("event_id"),
                    "sandbox": bool(getattr(billing_runtime, "sandbox", False))}
        result = {"applied": False, "reason": "event recorded only"}
        if event.event_type == "checkout.completed" and event.status == "paid" and event.tenant_id and event.plan_id:
            try:
                commercial_store.set_plan(event.tenant_id, event.plan_id)
                result = {"applied": True, "plan_id": event.plan_id,
                          "sandbox": bool(getattr(billing_runtime, "sandbox", False))}
            except KeyError:
                result = {"applied": False, "reason": "unknown plan"}
        commercial_store.complete_billing_event(provider=provider_id, event_key=event.event_key,
                                                status="processed", result=result)
        return {"ok": True, "duplicate": False, "result": result,
                "sandbox": bool(getattr(billing_runtime, "sandbox", False))}

    @router.post("/api/analytics/events")
    def record_analytics_event(req: AnalyticsEventRequest, principal=Depends(current_principal)):
        tenant_id = principal.tenant_id if principal.authenticated else settings.bootstrap_tenant_id
        commercial_store.track(tenant_id=tenant_id,
                               user_id=(principal.user_id if principal.authenticated else ""),
                               session_id=req.session_id, event_name=req.event_name, properties=req.properties)
        return {"ok": True}

    @router.get("/api/admin/analytics/summary")
    def analytics_summary(principal=Depends(require_roles("school_admin"))):
        return commercial_store.analytics_summary(principal.tenant_id)

    return router
