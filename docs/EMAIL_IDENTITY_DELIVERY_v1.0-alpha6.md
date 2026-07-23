# Email & Identity Delivery · v1.0-alpha6

## Providers

### Console

Development only. Writes a JSONL outbox and explicitly marks messages as not externally delivered.

### SMTP

Configuration:

```env
EMAIL_PROVIDER=smtp
EMAIL_FROM=no-reply@example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
SMTP_USE_SSL=false
PUBLIC_BASE_URL=https://app.example.com
```

Invitation and password-reset links are generated from `PUBLIC_BASE_URL`.

Non-demo production rejects `EMAIL_PROVIDER=console`.

## Security

- invitation/reset tokens remain hashed at rest;
- raw invitation tokens are removed from production API responses;
- SMTP failure does not falsely report successful external delivery;
- console outbox is a development artifact and must not be used as a production mailbox.
