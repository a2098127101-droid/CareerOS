# Supply-chain security

CareerOS treats dependency, container, secret, and release provenance evidence as
separate gates. A successful unit-test workflow is not a substitute for these
checks.

## Automated checks

The supply-chain workflow:

- audits the hash-locked Python dependency graph with `pip-audit`;
- emits JSON vulnerability evidence and a CycloneDX SBOM;
- scans the repository for high/critical vulnerabilities, secrets, and
  misconfiguration with Trivy;
- builds the release container from the pinned base image and scans that image;
- emits an image CycloneDX SBOM;
- attests a source archive with GitHub artifact attestation on `main` and manual
  runs.

All third-party workflow actions are pinned to immutable commit SHAs. Dependabot
is configured for Python, GitHub Actions, and Docker dependency updates.

## GitHub-native controls

Secret scanning, push protection, Dependabot alerts, and Dependabot security
updates should remain enabled in repository settings. A clean scan means that no
supported pattern was detected at scan time; it is not proof that no secret can
exist.

## Scope boundary

SBOM and vulnerability output describe the scanned source and image at a
specific commit. They do not certify the configuration, runtime environment,
model provider, data handling, or business workflow. Runtime and Business E2E
certificates remain separate, signed, environment-bound artifacts.
