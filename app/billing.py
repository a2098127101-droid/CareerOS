from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4


class BillingError(RuntimeError):
    pass


@dataclass(frozen=True)
class BillingEvent:
    event_key: str
    event_type: str
    tenant_id: str
    plan_id: str
    status: str
    payload: dict[str, Any]


class BillingProvider(Protocol):
    provider_id: str
    sandbox: bool

    def create_checkout(self, *, tenant_id: str, plan_id: str, success_url: str = "", cancel_url: str = "") -> dict[str, Any]: ...
    def verify_webhook(self, *, body: bytes, signature: str) -> BillingEvent: ...


class MockBillingProvider:
    """Development/sandbox provider only.

    It never claims to move real money. A signed mock webhook may transition a
    sandbox subscription for integration testing.
    """

    provider_id = "mock"
    sandbox = True

    def __init__(self, webhook_secret: str = ""):
        self.webhook_secret = webhook_secret

    def create_checkout(self, *, tenant_id: str, plan_id: str, success_url: str = "", cancel_url: str = "") -> dict[str, Any]:
        return {
            "checkout_id": f"MOCKCHK-{uuid4().hex[:16].upper()}",
            "tenant_id": tenant_id,
            "plan_id": plan_id,
            "provider": self.provider_id,
            "sandbox": True,
            "status": "requires_mock_webhook",
            "checkout_url": "",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "note": "Mock checkout only. No real payment has been created or captured.",
        }

    def verify_webhook(self, *, body: bytes, signature: str) -> BillingEvent:
        if not self.webhook_secret:
            raise BillingError("BILLING_WEBHOOK_SECRET is required for mock webhook verification")
        expected = hmac.new(self.webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(expected, signature.strip()):
            raise BillingError("invalid webhook signature")
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as exc:
            raise BillingError("invalid webhook JSON") from exc
        event_key = str(payload.get("event_id") or payload.get("id") or "").strip()
        if not event_key:
            raise BillingError("webhook event_id is required")
        event_type = str(payload.get("type") or "").strip()
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        tenant_id = str(data.get("tenant_id") or "").strip()
        plan_id = str(data.get("plan_id") or "").strip()
        status = str(data.get("status") or "").strip().lower()
        return BillingEvent(
            event_key=event_key,
            event_type=event_type,
            tenant_id=tenant_id,
            plan_id=plan_id,
            status=status,
            payload=payload,
        )


def build_billing_provider(provider: str, *, webhook_secret: str = "") -> BillingProvider:
    provider_id = (provider or "mock").strip().lower()
    if provider_id == "mock":
        return MockBillingProvider(webhook_secret=webhook_secret)
    raise BillingError(
        f"Billing provider '{provider_id}' is not implemented in v1.0-beta1. "
        "Only signed mock/sandbox billing is available; no real payment success may be claimed."
    )
