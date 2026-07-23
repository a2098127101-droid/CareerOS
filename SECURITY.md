# Security Policy

## Supported versions

| Version | Status |
| --- | --- |
| `main` | Security fixes are considered as the project evolves. |
| `v1.0-beta1` | Pre-release evaluation build; not supported for production use. |
| Older builds | Not supported. |

This repository does not currently provide a production security SLA.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities, credentials, personal data, or
exploit details in a public issue.

Use the repository's
[private vulnerability reporting form](../../security/advisories/new) when
available. Include the affected version or commit, reproduction steps,
impact, and any suggested mitigation. If private reporting is unavailable,
contact the repository owner through a private GitHub channel before public
disclosure.

The maintainers will validate reports and coordinate remediation and
disclosure when possible. No fixed acknowledgement or remediation deadline
is promised for this pre-release.

## Security boundaries

- Never commit `.env` files, secrets, access tokens, production data, signed
  runtime certificates, or customer-identifying information.
- Production deployments must use strong externally managed secrets and must
  enable authentication, tenant isolation, and fail-closed dependency checks.
- The packaged tests and local showcase do not constitute a production
  security certification.
