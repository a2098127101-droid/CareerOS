# Configurable Engines · v1.0-alpha7

## Workflow

The fixed default workflow is now one compatibility template rather than the only possible product flow.

Available presets:

| Preset | Template | Stages |
|---|---|---:|
| career_development | career_development_v1 | 10 |
| campus_career | campus_career_v1 | 10 |
| career_service | career_service_v1 | 7 |
| career_competition | career_competition_v1 | 10 |
| enterprise_talent | enterprise_talent_v1 | 7 |

API:

```text
GET /api/product/workflow-templates
```

Workflow instances persist `template_id`.

## Artifact

Built-in canonical kinds:

- resume
- career_report
- action_plan
- portfolio
- assessment
- development_report
- presentation
- mock_defense

API:

```text
GET /api/product/artifact-templates
```

Artifact metadata records template ID, renderer type and review rubric ID.

## Current boundary

This is a configurable **built-in engine foundation**, not a full arbitrary tenant template authoring platform. Persistent tenant-authored workflow/artifact CRUD, visual builder, custom transition expressions and arbitrary renderer execution remain future work.
