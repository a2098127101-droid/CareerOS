# CareerOS v1.3 Change Log

Version: `1.3.0-beta-unified-runtime`

## Unified Runtime

- Added a single H5 runtime boundary: `UI → Service → DataAdapter → FastAPI → Repository`.
- Migrated the H5 state authority for Evidence, Artifact, Task, User, Job, Knowledge, Interview, PPT state, notifications, chat history, usage events, settings and selected job.
- Added `LocalDemoAdapter` and `ApiAdapter` behind the same Service Registry.
- Added `CareerOSServices` for entity-oriented access and `CareerOSRuntime` for runtime-level sync/import/pull/push.
- API mode now treats FastAPI as authoritative. Browser storage is an optimistic/offline cache only.

## Persistence and tenancy

- Added `unified_runtime_entities` persistence with tenant, entity type, entity ID and owner-user scoping.
- Added SQLite `UnifiedRuntimeStore` and PostgreSQL-compatible `PostgresUnifiedRuntimeRepository`.
- Added owner-scoped collection replacement so one student cannot overwrite another student's private runtime entities.
- Tenant-shared collections such as user directory, knowledge and job records require staff write permission.

## API

Added runtime endpoints under `/api/runtime/v1`:

- `GET /state`
- `PUT /state/{state_key}`
- `DELETE /state`
- `POST /import`
- `GET /entities/{entity_type}`
- `GET /entities/{entity_type}/{entity_id}`
- `POST /entities/{entity_type}`
- `DELETE /entities/{entity_type}/{entity_id}`
- `PUT /collections/{state_key}`

## Migration and compatibility

- H5 local schema upgraded to v3.
- Existing v2 browser state is automatically copied to the v3 cache key on first read.
- Runtime Settings provide explicit `Push Local → API` and `Pull API → Local` operations.
- Switching to API mode preserves a pre-migration browser backup before the user chooses migration direction.
- Existing v1.2 Open API Gateway and provider adapters remain compatible.
- Alembic head remains `0007_tenant_templates_evidence_risk` for established repository test/release compatibility. The current baseline manifest includes the unified table; existing PostgreSQL installations already stamped at 0007 receive an idempotent repository `checkfirst` schema ensure. SQLite forward migration remains migration 17.

## Validation

- 141/141 repository tests passed in three non-overlapping groups.
- Browser runtime bridge verified backend persistence for Evidence, Artifact, Task, User, Job, Knowledge, Interview and Selected Job.
- A fresh frontend state successfully restored those entities from FastAPI.
- Granular Service → ApiAdapter → FastAPI CRUD was verified.
- JavaScript page/console errors in the runtime bridge test: 0.
