# CareerOS v1.2 → v1.3 Migration Guide

## 1. Back up before upgrade

Export the v1.2 H5 backup before switching runtime modes.

v1.3 also keeps a `careeros-pre-api-backup-v13` snapshot when the UI switches from Demo to API mode.

## 2. Browser state migration

v1.3 uses:

```text
careeros-showcase-state-v3
```

If this key is absent and the v1.2 key exists:

```text
careeros-showcase-state-v2
```

v1.3 copies the legacy value forward automatically. The old key is not treated as the API-mode source of truth after server synchronization.

## 3. SQLite migration

Run the existing CareerOS migration flow. Migration 17 creates `unified_runtime_entities` for legacy SQLite databases.

Verify:

```text
migration_status.current >= 17
```

## 4. PostgreSQL migration compatibility

The current schema manifest contains `unified_runtime_entities`, so a fresh baseline install creates it.

For installations already stamped at Alembic revision `0007_tenant_templates_evidence_risk`, the PostgreSQL unified runtime repository performs an idempotent `checkfirst` create from the versioned baseline metadata. This preserves existing Alembic-head compatibility while ensuring the v1.3 runtime table exists.

Before production use, verify the table and indexes:

```text
unified_runtime_entities
idx_unified_runtime_tenant_type_updated
idx_unified_runtime_owner
```

## 5. Choose migration direction

### Existing local demo data is authoritative

Use:

```text
Push Local → API
```

### Existing server data is authoritative

Use:

```text
Pull API → Local
```

Do not alternate directions without understanding overwrite semantics. Collection replacement is intentional and tenant/owner scoped.

## 6. Validate after migration

Check at minimum:

- Evidence persists after browser refresh/new session.
- Artifact persists.
- Tasks preserve IDs/status/origin metadata.
- Users and jobs are tenant scoped.
- Knowledge persists.
- Interview history persists.
- Selected Job persists.
- A second student cannot see or replace another student's private runtime entities.
- A different tenant cannot see the first tenant's runtime entities.

## 7. Rollback

The browser pre-switch backup can restore local demo state. Database rollback should use the normal environment backup/restore process; do not depend on deleting `unified_runtime_entities` in a production rollback without first exporting its data.
