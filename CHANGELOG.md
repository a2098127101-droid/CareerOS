# StepIn Changelog

## 2.2.0-beta-agent-trajectory · 2026-08-12

StepIn 2.2 is the current production `main` line. Historical CareerOS 1.x release notes, migration snapshots and development-stage audit reports have been removed from the active documentation surface; Git history remains the source for obsolete release records.

### Learner Agent becomes the core runtime

- Added standalone Learner Agent State, Policy, Tools, Memory, Execution Loop and Evaluation.
- Expanded the stable `/api/learner-agent/v1` contract to 13 routes.
- Kept LLM use inside the language/scaffolding layer; final work, gate bypass, mastery decisions and privileged tool selection remain prohibited.

### Real Learner Trajectory

- Server-side practice events now become learner observations instead of depending on an open chat window.
- Captured answer saves, hint requests, failures, completions, revisions, transfers, teacher feedback, Evidence decisions, project milestones and Agent interventions.
- Separated short-term session Memory from the long-term learner Trajectory.

### Bounded Policy Calibration

- Added trajectory-based challenge, hint-dependency, recovery, transfer, evidence and feedback metrics.
- Candidate policy profiles can adjust only bounded ASK / HINT / EXPLAIN / REQUEST_EVIDENCE / ESCALATE timing.
- Candidate profiles do not activate automatically and require administrator approval.

### Practice-first Project Library v2.2

- Replaced the old career-planning-first default template with a real-task comprehensive practice template.
- New projects use the current immutable v2.2 library version; historical projects continue to read the template version they were created with.
- Added task/material → information → judgment → V1 → feedback → V2 → transfer → evidence → reflection structure and project-library audit coverage.

### Production integration and validation

- PR #19 merged StepIn 2.2 into production `main`.
- Locked regression matrix: **204 / 204**.
- Learner Agent contract: 13 routes.
- Foundation contract: 10 routes.
- Project Library v2.2 audit added.
- Database-access, repository-contract, dependency, supply-chain and production-release gates retained.

### Current boundaries

- Pedagogical validity still requires real learner trajectories and human labels.
- Windows x64 installation, offline use, upgrade, backup and restore remain a separate release gate.
- Target production infrastructure certification remains separate from source-code CI.
