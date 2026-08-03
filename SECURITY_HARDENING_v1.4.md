# CareerOS v1.4 Security Hardening

## Completed
- Owner-scoped multi-user runtime key.
- Explicit subject-user authorization and advisor relationship checks.
- Canonical collection replacement disabled.
- Optimistic-lock protection on core participant mutations.
- Provider SSRF checks block loopback/private/link-local/reserved/metadata-style targets by default.
- Private/self-hosted provider networking requires explicit opt-in.
- Secret-like custom header/query keys are rejected from plaintext generic config; primary provider credentials remain encrypted/masked.
- API-mode AI failure is fail-closed (`503`) rather than fake output.

## Still required before internet-facing production
- Network-layer egress allowlist/firewall in addition to application SSRF checks.
- Managed KMS/secret vault for all production secrets.
- HTTPS termination, secure cookie/session policy, CSRF review and SSO/MFA policy as required.
- Rate limits/WAF and abuse controls.
- Independent security review and penetration test.
