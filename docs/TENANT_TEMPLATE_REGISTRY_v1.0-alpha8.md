# Tenant Template Registry · v1.0-alpha8

## Workflow lifecycle

```text
Built-in preset template
        │ fallback
        ▼
Tenant draft v1 ── edit ── activate
        │
        ├─ new sessions bind to v1
        │
        └─ historical sessions keep their existing workflow graph

Tenant draft v2 ── activate
        ├─ v1 → archived
        └─ new sessions bind to v2
```

The design deliberately prevents in-place mutation of active templates because changing a workflow already attached to historical sessions would corrupt auditability and completion semantics.

## Artifact lifecycle

Artifact templates follow draft → active → archived semantics by tenant and canonical `kind`. Tenant active definitions are evaluated before built-in fallback aliases.

## Tenant isolation

All registry queries are tenant-scoped. A template created by Organization A cannot be listed, resolved or activated by Organization B.

## Current limitation

alpha8 exposes API-level template administration and persistence. A visual drag/drop Workflow Builder, arbitrary executable transition expressions and custom renderer execution are not implemented yet.
