# StepIn 2.2 Test Report

## Current locked baseline

Canonical release identity is defined in `config/stepin_release_baseline.json`. The current production baseline is **Spatial Practice Alpha 7 · Adaptive Showcase** with **208 / 208 automated regression tests**, Capability Verification `2.0-min`, Python 3.11.9 and Node 22.12.0.

`scripts/audit_release_baseline.py` verifies that current public documentation, CI and Production Release workflows remain aligned with that canonical metadata. The locked test count is read from the baseline rather than duplicated as a separate CI constant.

## Spatial frontend gates

The spatial frontend has a deterministic dependency and build contract:

- `frontend/package-lock.json` is committed with lockfileVersion 3;
- fixed Node 22.12.0 is used in frontend CI/release workflows;
- CI regenerates the lock candidate and requires zero diff;
- CI and Production Release install through `npm ci --ignore-scripts --no-audit --no-fund`;
- TypeScript typecheck must pass;
- Vite production build must pass;
- `app/static/app/index.html` must exist as the FastAPI spatial bundle entry.

The root Docker image now follows the same source contract through a multi-stage build. A pinned Node builder performs `npm ci` and `npm run build`, and the final non-root Python runtime copies only the generated `app/static/app` bundle. Host-side `app/static/app` is excluded from the Docker context so stale build output cannot silently replace the deterministic builder result.

## Adaptive Showcase runtime validation

Alpha 7 preserves the full Showcase visual path while exposing explicit runtime budgets:

```text
auto
ultra
high
balanced
safe
```

These budgets control DPR, post-processing pixel ratio, SSR, depth-aware volumetric raymarching, Bloom, GPGPU topology size, instanced data count, CubeCamera resolution, reflector/transmission resolution, realtime shadows and sparkle density.

`auto` uses device heuristics plus runtime FPS sampling and only degrades when performance remains below budget. WebGL context loss persists the session to Safe and restoration does not automatically return to a higher-cost path.

This is runtime protection, not hardware certification. Windows WebView2 / Intel / AMD / NVIDIA multi-device testing remains a separate release gate.

## StepIn production gates

The current production line retains the following application contracts:

- Learner Agent action/tool boundaries, trajectory integration and human-activated calibration;
- Foundation production contract and beginner-gate behavior;
- Project Library v2.2 immutable-template behavior;
- Capability Verification 2.0-min conservative Signal / Evidence / Verified Evidence rules;
- Real Work Sample V1 → feedback → V2 → transfer server-phase guards;
- server-authoritative Evidence, Artifact, Capability and Trajectory state;
- SceneState read-only spatial presentation contract.

## Retained platform regression gates

The locked matrix also covers:

- Python application, migration and test compilation;
- deployment shell syntax and production Compose validation;
- canonical release-baseline audit;
- database-access boundary audit;
- repository-contract audit across supported repository implementations;
- tenant and authorization regressions;
- Evidence, Artifact, project, worker, storage, RAG/provider and production-runtime regressions;
- dependency consistency and supply-chain security scanning;
- deterministic production release ZIP and archive-boundary checks.

## Supply-chain and release checks

Current release validation includes:

- Python hash-locked dependency installation;
- Python dependency audit;
- Python CycloneDX SBOM;
- repository vulnerability, secret and misconfiguration scan;
- multi-stage release-container build from frontend source + lockfile;
- release-container vulnerability scan;
- image CycloneDX SBOM;
- frontend package-lock zero-drift check;
- deterministic frontend `npm ci`;
- release checksum validation;
- release manifest embedding the exact canonical baseline;
- verification that secrets, runtime databases and student data are excluded from the production archive.

Each PR Production Release artifact remains an engineering candidate with finite GitHub Actions retention. A durable public GitHub Release should be created only from a reviewed tag after target release notes and known limitations are finalized.

## Release boundary

The canonical baseline currently records `target_environment_certified=false` and `windows_webview2_certified=false`. Passing source, CI, container and release-package gates establishes build and engineering-contract consistency; it does **not** by itself certify pedagogical effectiveness, a specific external model provider, a target cloud environment, institutional privacy readiness, or universal Windows/GPU compatibility. Those remain separate validation and deployment gates.
