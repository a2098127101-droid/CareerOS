# StepIn Security Policy

## Supported version

Only the current `main` production line, StepIn `2.2.0-beta-agent-trajectory`, is actively maintained in this repository. Historical CareerOS 1.x development builds are superseded and are not supported deployment targets.

This repository does not currently provide a production security SLA.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities, credentials, personal data, or exploit details in a public issue. Use the repository's private vulnerability reporting form when available. Include the affected commit, reproduction steps, impact and any suggested mitigation. If private reporting is unavailable, contact the repository owner through a private GitHub channel before public disclosure.

## Security boundaries

- Never commit `.env` files, secrets, access tokens, production data, signed runtime certificates or customer-identifying information.
- Production deployments must use strong externally managed secrets and enable authentication, tenant isolation and fail-closed dependency checks.
- Candidate Learner Agent policy profiles cannot bypass authorization, Foundation/Project gates, Evidence verification or human escalation boundaries.
- Raw learner trajectories must not be aggregated across tenants for research or model training without separate authorization, de-identification and data-governance review.
- CI, packaged tests and local demonstrations do not constitute target-environment security certification.
- Real deployments must complete the current `deploy/PRODUCTION_CHECKLIST.md` and target-environment certification before public pilot traffic is opened.
