from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from app.billing import MockBillingProvider
from app.commercial_store import CommercialStore
from app.migrations import run_migrations, migration_status


def test_billing_migration_and_store_idempotency(tmp_path: Path):
    db = tmp_path / "billing.db"
    run_migrations(str(db))
    assert migration_status(str(db))["current"] >= 14
    store = CommercialStore(str(db))
    store.ensure_subscription("org-a", "free")
    order = store.create_billing_order(tenant_id="org-a", plan_id="professional")
    assert order["tenant_id"] == "org-a"
    body = json.dumps({"event_id":"evt-1","type":"checkout.completed","data":{"tenant_id":"org-a","plan_id":"professional","status":"paid"}}, separators=(",", ":")).encode()
    event, duplicate = store.record_billing_event(provider="mock",event_key="evt-1",event_type="checkout.completed",tenant_id="org-a",raw_payload=body)
    assert duplicate is False
    same, duplicate = store.record_billing_event(provider="mock",event_key="evt-1",event_type="checkout.completed",tenant_id="org-a",raw_payload=body)
    assert duplicate is True
    assert same["event_id"] == event["event_id"]


def test_mock_billing_signature_and_truthful_sandbox():
    secret = "test-secret"
    provider = MockBillingProvider(secret)
    checkout = provider.create_checkout(tenant_id="org-a", plan_id="professional")
    assert checkout["sandbox"] is True
    assert checkout["status"] == "requires_mock_webhook"
    assert checkout["checkout_url"] == ""
    body = json.dumps({"event_id":"evt-2","type":"checkout.completed","data":{"tenant_id":"org-a","plan_id":"professional","status":"paid"}}, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    event = provider.verify_webhook(body=body, signature=sig)
    assert event.event_key == "evt-2"
    assert event.status == "paid"
