# StepIn Spatial Runtime Telemetry · Alpha 8

Alpha 8 adds certification telemetry around the existing **Spatial Practice Alpha 7 · Adaptive Showcase** visual runtime. It does not create a new learning-state authority and does not change Capability Verification, Evidence, Artifact, Learner Trajectory or Learner Agent semantics.

## Runtime endpoints

```text
GET  /api/spatial-runtime/v1/telemetry/contract
POST /api/spatial-runtime/v1/telemetry
GET  /api/spatial-runtime/v1/telemetry/summary
```

Participants may submit render-only telemetry. Advisor/organization administrator roles may read the tenant-scoped process-window summary. The persistent analytics event is written with blank `user_id` and `session_id`.

Accepted data is allow-listed and limited to render/runtime information: quality tier and request, motion mode, FPS, P50/P95/P99 frametime, bucketed viewport, bucketed CPU/memory class, WebView flag, WebGL capability limits and a coarse renderer class such as Intel/AMD/NVIDIA/software. Raw GPU renderer strings and raw User-Agent strings are not submitted.

The endpoint rejects unknown fields, so learner answers, task material, Evidence text, messages, user IDs and session IDs cannot be smuggled into the telemetry payload through arbitrary JSON properties.

## Motion policy

Render quality and motion accessibility are now independent.

```text
/app?motion=full
/app?motion=reduced
/app?motion=off
```

Without an explicit parameter, `prefers-reduced-motion: reduce` selects reduced motion. `reduced` and `off` switch the R3F scene from a perpetual animation loop to demand rendering. The selected material/quality tier remains intact, so a user may keep high-fidelity materials without continuous camera, particle and room animation.

This replaces the previous behavior where reduced-motion preference merely forced the Safe quality tier.

## Certification events

The browser submits only these event types:

```text
boot
frame_sample
quality_change
context_lost
context_restored
```

Quality-change reasons are constrained to a small enum such as `webgl_capability`, `sustained_low_fps` and context-loss recovery. Frame samples are produced from the same four-second measurement windows that drive adaptive quality decisions.

## Privacy boundary

Spatial telemetry is certification evidence, not learner analytics. It must never contain:

- learner answers or chat content;
- task or source-material text;
- Evidence/Artifact payloads;
- Capability or Trajectory mutations;
- raw User-Agent or renderer strings;
- learner user/session identifiers.

Telemetry failure is fail-open for practice: a failed telemetry request must never block the learner from continuing a task.

## Remaining certification boundary

This implementation makes target-device measurements possible; it does not itself certify Windows/WebView2 or any GPU class. Real Intel/AMD/NVIDIA/WebView2 certification still requires running the target release on representative hardware and attaching the resulting runtime evidence to Issue #20.
