# Billing Foundation · v1.0-alpha5

## Status

Alpha5 implements **sandbox/mock billing only**.

There is no Stripe, WeChat Pay or Alipay live adapter and no real payment success is claimed.

## Implemented

- `BillingProvider` interface foundation.
- `MockBillingProvider`.
- Sandbox checkout object explicitly states no real payment was created.
- HMAC-SHA256 webhook verification.
- Billing event audit table.
- Webhook idempotency using `(provider, event_key)`.
- Sandbox plan transition after a correctly signed mock `checkout.completed` event.

## Configuration

```env
BILLING_ENABLED=false
BILLING_PROVIDER=mock
BILLING_WEBHOOK_SECRET=
```

Production validation rejects enabled real billing when only `mock` is configured.

## Future adapters

A real provider implementation must add:

- checkout/order creation
- signature verification
- idempotent webhook processing
- payment/subscription state reconciliation
- refunds
- auditability
- sandbox/live environment separation

A provider adapter must never trust browser-reported payment success.
