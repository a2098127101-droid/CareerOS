# CareerOS v1.3 Unified Runtime Guide

## Runtime modes

### Demo

`Runtime Mode = Demo · Local Adapter`

- No FastAPI persistence is required.
- Local browser state is authoritative.
- Suitable for offline demonstrations only.

### API

`Runtime Mode = API · FastAPI Unified Runtime`

- FastAPI is authoritative.
- Browser state is a cache/offline fallback.
- Runtime badge reports loading/sync/error status.

## Switching Demo → API

The UI stores a pre-switch backup and requires an explicit choice:

### Push Local → API

Use when the browser contains the data to preserve.

```text
Current local runtime state
→ POST /api/runtime/v1/import (replace)
→ FastAPI repository
→ Pull server snapshot
```

### Pull API → Local

Use when the server already contains authoritative data.

```text
GET /api/runtime/v1/state
→ replace cached runtime state
```

Do not use Push when an older local demo should not overwrite newer server data.

## Programmatic services

The H5 exposes:

```javascript
CareerOSServices.evidence
CareerOSServices.artifact
CareerOSServices.task
CareerOSServices.user
CareerOSServices.job
CareerOSServices.knowledge
CareerOSServices.interview
```

Common operations:

```javascript
await CareerOSServices.evidence.list();
await CareerOSServices.evidence.create(item);
await CareerOSServices.evidence.update(item);
await CareerOSServices.evidence.remove(item.id);
await CareerOSServices.evidence.replace(items);
await CareerOSServices.evidence.pull();
```

Runtime-level operations:

```javascript
await CareerOSRuntime.patch({...});
await CareerOSRuntime.flush();
await CareerOSRuntime.push();
await CareerOSRuntime.pull();
CareerOSRuntime.status();
```

`patch()` exists as the compatibility bridge for legacy H5 actions and should not replace entity-granular service methods in new code.

## Error handling

API synchronization errors:

- do not silently report success;
- set the runtime badge to `API · Sync error`;
- preserve the local optimistic cache;
- expose the last sync error through `CareerOSRuntime.status()`.

A later successful pull can reconcile the cache with the server.

## Security model

Runtime endpoints use the existing current-principal/authentication system.

- tenant isolation is mandatory;
- private participant entities are owner scoped;
- shared user/knowledge/job collections require staff writes;
- Provider credentials remain in the dedicated encrypted Provider Store, not unified runtime payloads.
