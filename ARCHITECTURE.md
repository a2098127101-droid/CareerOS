# StepIn 2.2 Architecture

StepIn 2.2 is a practice-first capability system for beginners. The production line is organized around **Learner Agent + Practice Runtime + Evidence/Artifact + Human Review**, rather than a course catalog or a generic career-coaching chat interface.

## Product runtime

```text
Real work task / material
  → Practice Runtime
  → Learner Agent observation and intervention
  → revision / transfer / evidence events
  → Learner Trajectory
  → Evaluation and bounded Policy Calibration
  → Human Review when required
  → Verified Evidence / capability confidence
```

The learner path is intentionally task-first: start doing, receive bounded support when blocked, revise after feedback, transfer the skill to different material, combine tasks into projects, and retain evidence of the work process.

## Learner Agent boundary

The Learner Agent owns State, Policy, Tools, Memory, Trajectory, Execution Loop, Evaluation and Calibration. Clients call the stable `/api/learner-agent/v1` contract instead of reproducing policy logic in the UI.

The LLM is a language layer, not the authority layer. It cannot independently select privileged tools, bypass Foundation or Project gates, generate the learner's final deliverable, mark capability as mastered, or activate a candidate policy. Candidate policy profiles require sufficient trajectory data and explicit administrator activation.

## Practice and evidence model

Foundation provides the beginner entry point and cross-material transfer. Project Library v2.2 uses immutable practice-first templates built around task constraints, source material, information processing, judgment, first delivery, feedback, revision, transfer, process evidence and reflection.

Evidence and Artifact remain canonical business objects. Capability claims should increasingly depend on repeated performance across different tasks, materials, support levels and time rather than a single completion event.

## Data and service boundaries

FastAPI is the production service boundary. The repository layer supports SQLite compatibility and PostgreSQL production containers. Production deployment retains tenant isolation, repository contracts, database-access audits, object storage, Redis worker and security gates from the existing runtime. Historical migration names and selected compatibility identifiers remain only where changing them would break upgrade paths or stored data; they are not current product branding.

## Current production validation

The StepIn 2.2 production baseline is locked at **204 automated tests**, with Learner Agent 13-route contract validation, Foundation 10-route validation, Project Library v2.2 audit, database-access audit, repository-contract audit, supply-chain security scanning and production release packaging.

These engineering gates do not establish pedagogical validity. Real learner trajectories, human labels, Windows x64 release certification and target-environment production certification remain separate evidence requirements.

## Canonical current documents

- `README.md` / `README.zh-CN.md`
- `ROADMAP.md`
- `docs/LEARNER_AGENT_RUNTIME_v2.1.md`
- `docs/LEARNER_TRAJECTORY_AND_CALIBRATION_v2.2.md`
- `TEST_REPORT.md`
- `SECURITY.md`
- `deploy/README_PRODUCTION.md`
- `deploy/PRODUCTION_CHECKLIST.md`
