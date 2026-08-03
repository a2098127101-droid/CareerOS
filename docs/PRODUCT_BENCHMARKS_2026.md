# CareerOS Product Benchmarks · 2026

## Purpose

CareerOS may study public products and repositories to understand interaction mechanisms, deployment patterns and operational controls. It must not copy source code, proprietary datasets, brand assets, page composition, text, icons or protected visual identity unless the relevant license and internal approval explicitly permit that use.

The product objective remains specific:

```text
help a university student choose a direction
→ collect verifiable experience and evidence
→ complete a real project
→ produce a resume or career artifact
→ review and revise it
```

A benchmark is retained only when it reduces user effort or improves evidence quality, operational control or deployment safety.

## Adopted mechanisms

### Project and task systems

Reference class: Linear, GitHub Issues and similar task-oriented products.

Adopted:

- one dominant next action rather than a feature catalogue;
- explicit state transitions;
- priority queues for staff intervention;
- immutable history for consequential changes;
- compact project summaries with drill-down details.

Not adopted:

- issue-tracker terminology exposed to students;
- dense keyboard-first interaction as the default;
- visual copying of proprietary layouts.

### Self-hosted resume builders

Reference class: Reactive Resume and comparable self-hosted resume tools.

Adopted:

- user-controlled artifact versions;
- private/self-hosted deployment as a supported institutional mode;
- export as a first-class end state;
- separation between content data and rendering templates.

Not adopted:

- template or renderer code copied from another project;
- claims that a generated resume is automatically accurate;
- design controls that distract from evidence collection.

### Job-description matching tools

Reference class: Resume Matcher and comparable JD-to-resume tools.

Adopted:

- compare a master profile against a specific target role;
- identify requirement, evidence and gap separately;
- preserve the original artifact while producing a role-specific version;
- make unsupported claims visible rather than silently filling them.

Not adopted:

- keyword score presented as hiring probability;
- fabricated metrics or experience;
- opaque single-number decisions without traceable evidence.

### Self-hosted AI workspaces

Reference class: Open WebUI and comparable multi-provider workspaces.

Adopted:

- provider-neutral model configuration;
- primary/fallback routes;
- institution-controlled deployment;
- role-specific workspaces;
- explicit model and knowledge configuration.

Not adopted:

- making model selection the central student experience;
- exposing infrastructure complexity to ordinary users;
- unrestricted provider use without tenant governance.

### LLM observability platforms

Reference class: Langfuse and comparable observability/evaluation systems.

Adopted:

- record model, task, token volume, latency, success and error;
- estimate cost only from configured price records;
- flag unpriced calls instead of treating them as free;
- retain audit events for consequential project and administrative actions;
- evaluate model quality independently from provider availability.

Not adopted:

- a cost estimate presented as an invoiced amount;
- prompt or trace retention that violates student-data minimization;
- global observability access that bypasses tenant scope.

## Product rules derived from the benchmark review

1. **Project first.** A student enters through a concrete project, not an empty chat box.
2. **Next action first.** Each main screen states the single task that moves the project forward.
3. **Evidence before generation.** Real experience, files and target-role requirements precede artifact generation.
4. **Version instead of overwrite.** Generated and revised artifacts retain their history.
5. **Human intervention by exception.** Teachers receive a prioritized queue, not a flat user directory.
6. **Cost is governed.** Unknown model prices remain unpriced; failures and fallback calls remain visible.
7. **Deployment is fail-closed.** Public launch requires authentication, PostgreSQL, Redis, private object storage, TLS and current certification evidence.
8. **No employment prediction claim.** Matching and scoring support decisions; they do not predict an offer or replace professional judgement.

## Review checklist for future borrowing

Before adopting a mechanism, record:

- the user problem it solves;
- why existing CareerOS behavior is insufficient;
- the relevant repository/product and license;
- whether code, assets or only an abstract mechanism are involved;
- tenant, privacy and audit implications;
- expected measurable benefit;
- rollback criteria if the mechanism increases complexity.
