# CareerOS product benchmark notes — v1.5.0-rc1

This file records mechanism-level references only. CareerOS does not copy source code, visual assets, trademarks, or product copy from the listed products.

| Reference mechanism | User problem | CareerOS implementation | Boundary |
|---|---|---|---|
| Linear-style next action and priority queue | Users do not know what to do next | Student workflow exposes one current next step; Teacher workspace prioritizes an intervention queue | State and copy are CareerOS-specific |
| GitHub Issues-style assignment/history | Feedback is lost or not attributable | AI Task Center, Teacher Feedback, audit events and tenant-scoped assignments | No GitHub code or branding is reused |
| Reactive Resume-style data/template separation | Editing a resume overwrites history | Artifact versions keep source data, template and historical versions separate | Export formats remain CareerOS-owned |
| Job-to-skill matching mechanism | A job requirement is mistaken for a student capability | Structured Job Store is matched against Evidence; missing skills stay missing | No external job dataset is copied |
| Open WebUI-style provider neutrality | One model outage blocks the workflow | Multi-Model Gateway with per-agent Primary/Fallback routes | Provider credentials remain server-side |
| Langfuse-style trace fields | AI cost and failure causes are invisible | Model usage records capture provider, model, tokens, latency, retries and pricing status | This is an internal data contract, not copied implementation |
| Notion-style project organization | Evidence and artifacts are scattered | Project, Evidence, Artifact and Workflow entities are linked server-side | No UI or copy is reproduced |
| Duolingo-style progressive tasking | Large goals feel unmanageable | Ten-stage workflow and one next action | No gamification assets are reused |
| Sentry-style event context | Errors lack actionable context | Audit/error events retain tenant, actor, resource and operation context | No Sentry code or assets are bundled |

## License and IP rule

Only abstract interaction mechanisms are referenced. Any future implementation must use original CareerOS code, copy, icons and visual assets, and must preserve compatible licenses for dependencies.
