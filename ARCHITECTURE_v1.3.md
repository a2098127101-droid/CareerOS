# CareerOS v1.3 Architecture

## 1. Runtime authority

v1.3 removes the previous H5 authority split.

```text
CareerOS Unified H5
        │
        ▼
Domain / Entity Services
        │
        ▼
DataAdapter
   ┌────┴───────────┐
   │                │
LocalDemoAdapter   ApiAdapter
   │                │
Browser demo       FastAPI /api/runtime/v1
cache/state             │
                        ▼
                Unified Runtime Repository
                 ┌──────┴──────┐
                 │             │
               SQLite      PostgreSQL
```

In `demo` mode, `LocalDemoAdapter` is authoritative.

In `api` mode, FastAPI is authoritative. The browser still keeps an optimistic/offline cache so the UI can render while disconnected, but a successful `Pull API → Local` replaces cached runtime entities with the server snapshot.

## 2. Service Registry

The H5 exposes a unified service registry:

```text
CareerOSServices.artifact
CareerOSServices.evidence
CareerOSServices.task
CareerOSServices.user
CareerOSServices.job
CareerOSServices.knowledge
CareerOSServices.interview
```

Each runtime entity service supports the common boundary:

```text
list
create
update
remove
replace
pull
```

Legacy H5 actions that still write collections are intercepted by the v1.3 runtime bridge and synchronized through the same adapter. This prevents the old UI from bypassing FastAPI while allowing incremental conversion to granular service calls.

## 3. Unified Runtime entities

Frontend state keys are mapped to stable backend entity types:

| H5 state | Backend entity type | Shape |
| --- | --- | --- |
| artifacts | artifacts | collection |
| evidence | evidence | collection |
| users | users | collection |
| tasks | tasks | collection |
| knowledge | knowledge | collection |
| interviews | interviews | collection |
| pptSlides | ppt_slides | collection |
| pptReviews | ppt_reviews | collection |
| jobRows | jobs | collection |
| jobImports | job_imports | collection |
| notifications | notifications | collection |
| chatMessages | chat_messages | collection |
| usageEvents | usage_events | collection |
| settings | settings | singleton |
| selectedJob | selected_job | singleton |

## 4. Tenant and owner isolation

The repository primary key is:

```text
tenant_id + entity_type + entity_id
```

Private participant runtime entities are additionally scoped by `owner_user_id`.

Staff roles may read tenant-wide state. Student/private reads and replacements are owner scoped. Tenant-shared collections (`users`, `knowledge`, `jobs`, `job_imports`) require staff write access.

This prevents a collection replace from one student deleting another student's entities.

## 5. State synchronization

### API startup

```text
H5 boot
→ read local cache
→ detect runtimeMode=api
→ GET /api/runtime/v1/state
→ replace runtime state from server
→ preserve only local connection/bootstrap settings required to reach the API
→ render
```

### UI mutation in API mode

```text
UI action
→ Service-compatible state mutation
→ optimistic local cache update
→ RuntimeEntityService / DataAdapter
→ PUT/POST FastAPI
→ repository persistence
→ runtime status badge: Syncing / Synced / Sync error
```

### Migration from local demo

```text
Switch Demo → API
→ save pre-API browser backup
→ choose Push Local → API or Pull API → Local
→ explicit migration
```

No silent overwrite is performed during the mode switch.

## 6. Relationship to legacy backend stores

v1.3 eliminates the **H5 browser-local versus real-backend authority split**. It does not delete all historical backend stores.

Legacy Session, Agent Workflow, Artifact/Evidence workflow tables and other canonical services remain because they support established API/workflow behavior and earlier compatibility contracts. The Unified Runtime is now the H5 product-state authority in API mode; future work may progressively bridge selected runtime entities into deeper canonical domain stores where richer relational semantics are required.

This distinction prevents a false claim that every historical persistence table was physically consolidated into one database table.

## 7. Open API Gateway

The v1.2 vendor-neutral Provider Gateway remains unchanged in principle and can coexist with the unified runtime:

```text
AI Feature
→ Model Gateway
→ Provider Adapter
→ OpenAI-compatible / Responses / Anthropic / Gemini / Custom REST / OAuth2-protected enterprise API
```

Provider configuration remains server-side in API mode; secrets are not moved into the unified browser cache.
