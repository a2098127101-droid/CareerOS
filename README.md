# StepIn 2.2 Beta

**Start with real work. Turn every attempt, failure, revision, feedback event, and transfer into evidence for the next learning decision.**

**从一件简单真实的工作开始，让每次尝试、失败、修改、反馈和迁移都成为下一步教学决策的依据。**

[中文说明](README.zh-CN.md) · [Architecture](ARCHITECTURE.md) · [Roadmap](ROADMAP.md) · [Test status](TEST_REPORT.md) · [Runtime Telemetry](docs/SPATIAL_RUNTIME_TELEMETRY_ALPHA8.md) · [Learner Agent Runtime](docs/LEARNER_AGENT_RUNTIME_v2.1.md) · [Trajectory & Calibration](docs/LEARNER_TRAJECTORY_AND_CALIBRATION_v2.2.md)

## Product definition

StepIn is a practice-first learner-agent platform for learners with little or no internship or project experience. It does not begin with a course catalog, job assessment, badge collection or generic career-coach chat. It begins with one simple, realistic task the learner can attempt immediately.

**Start → follow an example → work independently → fail and get diagnosed → revise from feedback → transfer to a new context → combine tasks into projects → accumulate verified capability evidence → explain what you actually did.**

## Current production core

StepIn 2.2 is organized around **Learner Agent + Practice Runtime + Evidence/Artifact + Human Review**. The Learner Agent has independent State, Policy, Tools, Memory, Trajectory, Execution Loop, Evaluation and bounded Calibration, exposed through `/api/learner-agent/v1`.

The LLM is a language and scaffolding layer. It cannot independently select privileged tools, bypass server gates, generate the learner's final deliverable, verify Evidence, promote Capability or activate candidate policy profiles.

Server-side practice events become Agent observations even when the learner is not using a chat window. The trajectory covers saves, hints, failures, completions, revisions, transfer tasks, teacher feedback, Evidence decisions, project milestones, human review and Agent interventions. Short-term Memory and long-term Trajectory remain separate.

## Capability Verification 2.0

Capability state is server-authoritative and uses four conservative levels:

```text
unobserved
signal
evidence
verified_evidence
```

Evidence requires multiple distinct successful task contexts plus independence, revision, transfer or combined practice signals. `verified_evidence` additionally requires successful transfer and canonical Evidence with `VERIFIED` status. Multiple versions from one task cannot be counted as multiple contexts, and frontend interaction cannot promote capability.

## Real Work Sample runtime

The current Real Work Sample implements the full server-side practice path:

```text
ready
→ working_v1
→ revision_required
→ transfer_ready
→ completed
```

V1 creates an Artifact/Evidence record and deterministic supervisor feedback. V2 must materially improve the work and pass server validation. Transfer uses new material and no hints. Work Sample completion is not automatically equivalent to Verified Evidence.

## Spatial Practice Alpha 7 · Adaptive Showcase

`/app` uses the **Alpha 7 Adaptive Showcase** visual runtime, now surrounded by the **Alpha 8 Runtime Telemetry** certification layer. The high-fidelity 3D presentation remains server-driven and is built with React 19, React Three Fiber, Drei and Three.js.

The current visual system includes:

- custom WebGL shader workstations and control screens;
- transmission glass, dynamic CubeCamera reflections and reflective architecture;
- SSR, depth-aware volumetric raymarching, Bloom and fullscreen transition shaders;
- server-driven Evidence → Capability energy flow;
- GPU-instanced data fields and GPGPU capability topology reflow;
- Capability awakening sequences;
- V1 / feedback / V2 / transfer Artifact assembly and destruction choreography;
- timeline-based cinematic camera, lighting and room-transformation tracks;
- automated Showcase recording mode.

Showcase recording mode:

```text
/app?demo=1
/app?showcase=1
```

The demo only choreographs camera, lighting, topology, room, Artifact and post-processing state. It does **not** mutate server learning data and is explicitly marked as a visual rehearsal.

## Adaptive render budget

Alpha 7 keeps the full Alpha 6 visual path as `ultra`, while adding production-oriented runtime budgets:

```text
/app?quality=auto
/app?quality=ultra
/app?quality=high
/app?quality=balanced
/app?quality=safe
/app?qualitydebug=1
```

`auto` evaluates hardware concurrency, device memory, pixel load, WebView indicators and WebGL capabilities, then samples runtime FPS. Automatic quality only moves downward when performance remains below budget; it does not oscillate back upward during the session.

- **Ultra**: SSR + volumetric + Bloom, 48×48 GPGPU topology, 1,800 instanced data points.
- **High**: SSR + volumetric + Bloom, 40×40 topology, 1,200 data points.
- **Balanced**: 32×32 topology, 720 data points, SSR/volumetric disabled, Bloom retained.
- **Safe**: DPR capped at 1, 24×24 topology, 320 data points, SSR/volumetric/Bloom and realtime shadows disabled.

WebGL context loss forces the current session to Safe and remains Safe after restoration rather than immediately restarting the highest-cost GPU path.

## Motion accessibility

Render quality and motion are independent. A user may retain Ultra materials while disabling continuous animation:

```text
/app?motion=full
/app?motion=reduced
/app?motion=off
```

Without an explicit motion parameter, `prefers-reduced-motion: reduce` selects reduced motion. Reduced/off modes move React Three Fiber from a perpetual animation loop to demand rendering, so state and pointer invalidations can still render a fresh frame without continuous camera, particle or room motion.

## Alpha 8 runtime telemetry

The certification layer records only render/runtime information through:

```text
GET  /api/spatial-runtime/v1/telemetry/contract
POST /api/spatial-runtime/v1/telemetry
GET  /api/spatial-runtime/v1/telemetry/summary
```

Accepted fields are allow-listed: quality tier/request, motion mode, FPS, P50/P95/P99 frametime, bucketed viewport/device characteristics, WebView flag, WebGL capability limits and a coarse renderer class. Raw User-Agent strings, raw GPU renderer strings, learner answers, task material, Evidence text, user IDs and session IDs are not accepted. Telemetry is certification evidence only and never mutates learning state.

## Server authority boundary

The 3D runtime is intentionally presentation-only:

```text
source = server
readOnly = true
clientMayPromoteCapability = false
clientMayVerifyEvidence = false
clientMayRewriteTrajectory = false
```

Camera movement, shaders, lighting, particles, quality tiers, motion policy, telemetry and cinematic sequences never award learning progress.

## Production validation

The current production baseline enforces **208 / 208 automated regression tests**. The release gates also include:

- canonical StepIn release-baseline audit;
- Alpha 8 spatial-runtime telemetry/privacy audit;
- frontend lockfile zero-drift validation;
- deterministic `npm ci` installation;
- TypeScript typecheck and Vite production build;
- FastAPI spatial bundle entry verification;
- Foundation, Learner Agent and Project Library audits;
- database-access and repository-contract audits;
- dependency audit and CycloneDX SBOM generation;
- repository vulnerability / secret / misconfiguration scanning;
- source multi-stage release-container build and vulnerability scan;
- deterministic production ZIP and archive-boundary validation.

The frontend commits `frontend/package-lock.json`, CI/Production Release use `npm ci`, and the source Dockerfile builds the Spatial bundle from the same lockfile. Engineering gates establish code and release-contract consistency; they do not establish pedagogical effectiveness or universal GPU compatibility. Real pilot-environment and Windows WebView2 / Intel / AMD / NVIDIA hardware certification remain separate evidence tasks tracked in Issue #20.

## Quick start

### Windows

```text
OPEN_StepIn.cmd
```

### Python backend

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Spatial frontend

```bash
cd frontend
npm ci
npm run typecheck
npm run build
```

The Vite build is emitted into the FastAPI spatial bundle location used by `/app`. Local demo-account settings are documented in `.env.example`; do not enable demo seeding in production.
