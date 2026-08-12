# StepIn Supply-chain Security

StepIn treats dependency, container, secret and release-provenance evidence as separate production gates. A successful application test run is not a substitute for these checks.

## Automated checks

The current supply-chain workflow:

- audits the hash-locked Python dependency graph with `pip-audit`;
- emits vulnerability evidence and a CycloneDX Python SBOM;
- scans repository source for high/critical vulnerabilities, secrets and misconfiguration with Trivy;
- builds and scans the current `stepin:<commit>` release container;
- emits a StepIn container CycloneDX SBOM;
- creates and attests a `stepin-source-<commit>.tar.gz` source archive on non-PR runs.

Third-party workflow actions are pinned to immutable commit SHAs. Dependabot remains responsible for proposing current Python, GitHub Actions and Docker dependency updates.

## GitHub-native controls

Secret scanning, push protection, Dependabot alerts and Dependabot security updates should remain enabled in repository settings. A clean automated scan means no supported pattern was detected at scan time; it is not proof that a secret or vulnerability cannot exist.

## Scope boundary

SBOM and vulnerability evidence describe a specific source commit and container image. They do not certify the target deployment configuration, external model provider, learner-data governance, pedagogical validity, Windows x64 installation or business workflow. Those remain separate current release gates.
