# Architecture

CareerOS uses a dual-delivery model:

```text
Showcase Edition                    Production Edition
single static HTML                  FastAPI runtime
Demo Scenario                       Auth/RBAC/Tenant
no secrets                          Multi-model Gateway
no backend                          Evidence/Workflow/Artifacts
                                    RAG/Jobs/Storage/Commercial
```

## Domain abstraction

The platform core is independent from a single event or institution. Product Presets control tenant-facing labels and optional workflow behavior:

- career_development
- campus_career
- career_service
- career_competition (optional)

## Current data runtime

SQLite is still the active repository implementation. PostgreSQL is the next production migration target. `DATABASE_URL` does not mean the repository migration is complete.
