# StepIn 2.2 Test Report

## Current locked baseline

The current production `main` baseline enforces **208 / 208 automated regression tests** and fails if the locked count or any regression batch does not pass.

The latest fully validated spatial production baseline is **Spatial Practice Alpha 7 · Adaptive Showcase**, merged through PR #25. Alpha 7 adds adaptive GPU budgets, WebGL context-loss recovery and deterministic frontend dependency installation without weakening the existing backend contracts.

## Spatial frontend gates

The spatial frontend now has a deterministic dependency contract:

- `frontend/package-lock.json` is committed with lockfileVersion 3;
- fixed Node 22.12.0 is used in the frontend integrity workflow;
- CI regenerates the lock candidate and requires zero diff;
- CI and Production Release install through `npm ci --ignore-scripts --no-audit --no-fund`;
- TypeScript typecheck must pass;
- Vite production build must pass;
- `app/static/app/index.html` must exist as the FastAPI spatial bundle entry.

The previous `npm install --package-lock=false` build path has been removed from CI and release packaging.

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
- Capability Verification 2.0 conservative Signal / Evidence / Verified Evidence rules;
- Real Work Sample V1 → feedback → V2 → transfer server-phase guards;
- server-authoritative Evidence, Artifact, Capability and Trajectory state;
- SceneState read-only spatial presentation contract.

## Retained platform regression gates

The locked matrix also covers:

- Python application, migration and test compilation;
- deployment shell syntax and production Compose validation;
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
- release-container build;
- release-container vulnerability scan;
- image CycloneDX SBOM;
- frontend package-lock zero-drift check;
- deterministic frontend `npm ci`;
- release checksum validation;
- verification that secrets, runtime databases and student data are excluded from the production archive.

The latest validated Alpha 7 Production Release Artifact from PR #25 is `stepin-production-v2.2.0-pr25`.

## Release boundary

Passing these gates establishes source-code, build, dependency and engineering-contract consistency. It does **not** by itself certify pedagogical effectiveness, a specific external model provider, a target cloud environment, institutional privacy readiness, or universal Windows/GPU compatibility. Those remain separate validation and deployment gates.
