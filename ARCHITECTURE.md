# StepIn 2.2 Architecture

StepIn 2.2 is a practice-first capability system for beginners. The production line is organized around **Learner Agent + Practice Runtime + Evidence/Artifact + Human Review**, while the current spatial presentation layer is **Spatial Practice Alpha 7 · Adaptive Showcase**.

## Product runtime

```text
Real work task / material
  → Practice Runtime
  → Learner Agent observation and bounded intervention
  → revision / transfer / evidence events
  → Learner Trajectory
  → Evaluation and bounded Policy Calibration
  → Human Review when required
  → Capability Verification 2.0-min
  → server-authoritative SceneState
  → Spatial Practice read-only presentation
```

The learner path is intentionally task-first: start doing, receive bounded support when blocked, revise after feedback, transfer the skill to different material, combine tasks into projects, and retain evidence of the work process.

## Learner Agent boundary

The Learner Agent owns State, Policy, Tools, Memory, Trajectory, Execution Loop, Evaluation and Calibration. Clients call the stable `/api/learner-agent/v1` contract instead of reproducing policy logic in the UI.

The LLM is a language layer, not the authority layer. It cannot independently select privileged tools, bypass Foundation or Project gates, generate the learner's final deliverable, verify Evidence, promote Capability or activate a candidate policy. Candidate policy profiles require sufficient trajectory data and explicit administrator activation.

## Practice, evidence and capability model

Foundation provides the beginner entry point and cross-material transfer. Project Library v2.2 uses immutable practice-first templates built around task constraints, source material, information processing, judgment, first delivery, feedback, revision, transfer, process evidence and reflection.

Evidence and Artifact remain canonical business objects. Capability Verification 2.0-min derives conservative `unobserved / signal / evidence / verified_evidence` states from server-side task contexts, revision/independence/transfer signals and verified canonical Evidence. The spatial client may render these states but cannot promote them.

## Spatial presentation boundary

Alpha 7 is a high-fidelity server-driven presentation layer. It includes adaptive `auto / ultra / high / balanced / safe` render budgets, GPGPU topology, GPU instancing, SSR/volumetric/Bloom on higher tiers, cinematic sequencing, Artifact choreography and room transformation.

The SceneState authority contract remains read-only:

```text
source = server
readOnly = true
clientMayPromoteCapability = false
clientMayVerifyEvidence = false
clientMayRewriteTrajectory = false
```

Quality selection, FPS sampling, context-loss recovery, camera motion, shader state and showcase animation do not change Evidence, Artifact, Capability or Trajectory truth.

## Build and service boundaries

FastAPI is the production service boundary. The repository layer supports SQLite compatibility and PostgreSQL production containers. Production deployment retains tenant isolation, repository contracts, database-access audits, object storage, Redis worker and security gates.

The root `Dockerfile` is a multi-stage build. A pinned Node 22.12 builder performs deterministic `npm ci` and produces `app/static/app`; the Python runtime image then copies that spatial bundle into the final non-root container. Host-side `app/static/app` is excluded from the Docker context so stale build output cannot replace the builder result. Source Docker builds and Production Release packages therefore use the same frontend source and lockfile contract.

## Canonical release baseline

Release identity is defined in:

```text
config/stepin_release_baseline.json
```

The current baseline records StepIn `2.2.0`, **Spatial Practice Alpha 7 · Adaptive Showcase**, Capability Verification `2.0-min`, and **208 / 208** locked regression tests. `scripts/audit_release_baseline.py` prevents current public documentation and release workflows from silently drifting away from this metadata.

The release manifest embeds the same canonical baseline. Target-environment certification and Windows/WebView2 certification remain explicit booleans and are currently false until corresponding evidence exists.

## Current production validation

The current engineering baseline is locked at **208 / 208 automated regression tests**, with deterministic frontend lock/install checks, TypeScript/Vite build, Learner Agent, Foundation, Project Library, database/repository audits, supply-chain security scanning, release-container scanning and deterministic Production Release packaging.

These engineering gates do not establish pedagogical validity, real target-environment readiness or universal Windows/GPU compatibility. Real learner trajectories with human labels, pilot environment certification and Windows/WebView2 hardware certification remain separate evidence requirements.

## Canonical current documents

- `config/stepin_release_baseline.json`
- `README.md` / `README.zh-CN.md`
- `ROADMAP.md`
- `TEST_REPORT.md`
- `docs/LEARNER_AGENT_RUNTIME_v2.1.md`
- `docs/LEARNER_TRAJECTORY_AND_CALIBRATION_v2.2.md`
- `SECURITY.md`
- `deploy/README_PRODUCTION.md`
- `deploy/PRODUCTION_CHECKLIST.md`
