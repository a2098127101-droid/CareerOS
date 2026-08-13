# StepIn 2.2 Test Report

## Current locked baseline

Canonical release identity is defined in `config/stepin_release_baseline.json`. The current visual production baseline remains **Spatial Practice Alpha 7 · Adaptive Showcase** with **208 / 208 automated regression tests**, Capability Verification `2.0-min`, Python 3.11.9 and Node 22.12.0. Alpha 8 adds runtime-certification telemetry and independent motion accessibility without changing the server learning-state authority.

`scripts/audit_release_baseline.py` verifies that public documentation, effective FastAPI runtime identity, CI and Production Release remain aligned with canonical metadata. The locked test count is read from the baseline rather than duplicated as a CI constant.

## Spatial frontend gates

The spatial frontend has a deterministic dependency and build contract:

- `frontend/package-lock.json` is committed with lockfileVersion 3;
- fixed Node 22.12.0 is used in frontend CI/release workflows;
- CI regenerates the lock candidate and requires zero diff;
- CI and Production Release install through `npm ci --ignore-scripts --no-audit --no-fund`;
- TypeScript typecheck must pass;
- Vite production build must pass;
- `app/static/app/index.html` must exist as the FastAPI spatial bundle entry.

The root Docker image follows the same source contract through a multi-stage build. A pinned Node builder performs `npm ci` and `npm run build`, and the final non-root Python runtime copies only the generated `app/static/app` bundle. Host-side `app/static/app` is excluded from the Docker context so stale build output cannot silently replace the deterministic builder result.

## Adaptive Showcase runtime validation

Alpha 7 preserves the full Showcase visual path while exposing `auto / ultra / high / balanced / safe` budgets. They control DPR, post-processing pixel ratio, SSR, depth-aware volumetric raymarching, Bloom, GPGPU topology size, instanced data count, CubeCamera resolution, reflector/transmission resolution, realtime shadows and sparkle density.

`auto` uses device heuristics plus runtime FPS sampling and only degrades when performance remains below budget. WebGL context loss persists the session to Safe and restoration does not automatically return to a higher-cost path.

## Alpha 8 runtime telemetry/privacy gate

`scripts/audit_spatial_runtime_telemetry.py` is now a required CI and Production Release gate. It verifies:

- the telemetry server sanitizer accepts only the documented render/runtime schema;
- unknown fields such as learner answer/message/Evidence/task material/user/session identifiers are rejected;
- telemetry contract declares no learner-content acceptance and no learning-state mutation;
- the StepIn registration surface includes the telemetry API and canonical runtime version override;
- the frontend records boot, frame sample, quality downgrade and context-loss/restore events;
- raw renderer/User-Agent values are not submitted;
- reduced-motion is no longer coupled to quality downgrade;
- reduced/off motion uses R3F demand rendering rather than a perpetual animation loop.

The browser submits FPS and P50/P95/P99 frametime from the same four-second windows used by adaptive quality. Device/GPU fields are deliberately coarse: bucketed viewport/CPU/memory, WebView flag, WebGL limits and renderer class such as Intel/AMD/NVIDIA/software.

The server writes persistent analytics events with blank `user_id` and `session_id`. A bounded tenant process-window summary is available to advisor/organization/platform administrator roles. This telemetry never becomes SceneState, Evidence, Artifact, Capability, Trajectory or Learner Agent state.

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

The locked matrix also covers Python application/migration/test compilation, deployment shell syntax, production Compose validation, canonical release-baseline audit, database-access boundary audit, repository-contract audit, tenant/authorization regressions, Evidence/Artifact/project/worker/storage/RAG/provider regressions and deterministic production packaging.

## Supply-chain and release checks

Current release validation includes Python hash-locked dependency installation, dependency audit, Python CycloneDX SBOM, repository vulnerability/secret/misconfiguration scan, multi-stage release-container build from frontend source + lockfile, container vulnerability scan, image CycloneDX SBOM, frontend lockfile zero-drift, deterministic `npm ci`, Alpha 8 telemetry/privacy audit, checksum validation, embedded canonical baseline and archive-boundary checks excluding secrets/runtime databases/student data.

Each PR Production Release artifact remains an engineering candidate with finite GitHub Actions retention. A durable public GitHub Release should be created only from a reviewed tag after target release notes and known limitations are finalized.

## Release boundary

The canonical baseline still records `target_environment_certified=false` and `windows_webview2_certified=false`. Passing source, CI, telemetry-contract, container and release-package gates proves engineering-contract consistency and makes real device measurement possible. It does **not** itself certify pedagogical effectiveness, a specific external model provider, a target cloud environment, institutional privacy readiness or universal Windows/GPU compatibility. Those require target-environment evidence in Issue #20.
