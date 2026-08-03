from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import UnifiedRuntimeCollectionReplace, UnifiedRuntimeEntityUpsert, UnifiedRuntimeImportRequest, UnifiedRuntimeStateValue
from ..unified_runtime_store import RuntimeVersionConflict

# v1.4: canonical business domains have dedicated stores/services. The generic runtime repository is
# limited to UI/session-support state and offline-compatible records that do not have a canonical
# domain repository yet.
RUNTIME_STATE_SPECS: dict[str, tuple[str, str]] = {
    "interviews": ("interviews", "collection"),
    "pptSlides": ("ppt_slides", "collection"),
    "pptReviews": ("ppt_reviews", "collection"),
    "notifications": ("notifications", "collection"),
    "chatMessages": ("chat_messages", "collection"),
    "usageEvents": ("usage_events", "collection"),
    "settings": ("settings", "singleton"),
    "selectedJob": ("selected_job", "singleton"),
}
ENTITY_TO_STATE_KEY = {entity: key for key, (entity, _shape) in RUNTIME_STATE_SPECS.items()}
ALLOWED_ENTITY_TYPES = frozenset(ENTITY_TO_STATE_KEY)

# Legacy v1 entity names retained only so older clients receive an explicit migration error rather
# than silently writing a second source of truth.
CANONICAL_ENTITY_TYPES = frozenset({"artifacts", "evidence", "users", "tasks", "knowledge", "jobs", "job_imports"})
LEGACY_ALL_TYPES = ALLOWED_ENTITY_TYPES | CANONICAL_ENTITY_TYPES


def build_unified_runtime_router(*, repository: Any, current_principal: Callable, canonical_role: Callable, auth_store: Any) -> APIRouter:
    router = APIRouter(tags=["unified-runtime"])

    def tenant_id(principal) -> str:
        return principal.tenant_id

    def role(principal) -> str:
        return canonical_role(principal.role)

    def is_staff(principal) -> bool:
        return bool(principal.is_super_admin or role(principal) in {"organization_admin", "advisor"})

    def _target_in_tenant(subject_user_id: str, principal) -> bool:
        if not subject_user_id:
            return False
        try:
            memberships = auth_store.memberships(subject_user_id)
        except Exception:
            return False
        return any(m.get("tenant_id") == principal.tenant_id and m.get("status", "active") == "active" for m in memberships)

    def can_access_subject(principal, subject_user_id: str) -> bool:
        if not subject_user_id or subject_user_id == principal.user_id:
            return True
        if not _target_in_tenant(subject_user_id, principal):
            return False
        if principal.is_super_admin or role(principal) == "organization_admin":
            return True
        if role(principal) == "advisor":
            advisor_groups = auth_store.user_class_ids(principal.user_id, principal.tenant_id, role="teacher")
            student_groups = auth_store.user_class_ids(subject_user_id, principal.tenant_id, role="student")
            return bool(advisor_groups & student_groups)
        return False

    def resolve_owner(principal, subject_user_id: str = "") -> str:
        target = (subject_user_id or principal.user_id or "demo-local").strip()
        if not can_access_subject(principal, target):
            raise HTTPException(status_code=403, detail="subject user access denied")
        return target

    def normalize_item(item: dict[str, Any], index: int, entity_type: str) -> dict[str, Any]:
        out = dict(item or {})
        entity_id = str(out.get("id") or out.get("entity_id") or "").strip()
        if not entity_id:
            entity_id = f"{entity_type.upper()}-{index + 1}"
        out["id"] = entity_id
        return out

    def _conflict(exc: RuntimeVersionConflict) -> HTTPException:
        return HTTPException(
            status_code=409,
            detail={"code": "version_conflict", "entity_id": exc.entity_id, "expected": exc.expected, "actual": exc.actual},
        )

    # ---------------- v2 safe runtime API ----------------
    @router.get("/api/runtime/v2/revision")
    def runtime_revision(principal=Depends(current_principal)):
        return {"ok": True, "revision": repository.current_revision(tenant_id=tenant_id(principal))}

    @router.get("/api/runtime/v2/state")
    def runtime_state_v2(subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        owner = resolve_owner(principal, subject_user_id)
        data: dict[str, Any] = {}
        for state_key, (entity_type, shape) in RUNTIME_STATE_SPECS.items():
            rows = repository.list_all(tenant_id=tenant_id(principal), entity_type=entity_type, owner_user_id=owner)
            data[state_key] = (rows[0].get("value") if rows else None) if shape == "singleton" else rows
        return {
            "ok": True, "mode": "api", "schemaVersion": 4, "tenant_id": tenant_id(principal),
            "subject_user_id": owner, "revision": repository.current_revision(tenant_id=tenant_id(principal)), "data": data,
        }

    @router.get("/api/runtime/v2/entities/{entity_type}")
    def list_entities_v2(
        entity_type: str,
        subject_user_id: str = Query(default=""),
        limit: int = Query(default=200, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
        principal=Depends(current_principal),
    ):
        if entity_type not in ALLOWED_ENTITY_TYPES:
            raise HTTPException(status_code=404, detail="unknown runtime entity type; use canonical workspace API for business domains")
        owner = resolve_owner(principal, subject_user_id)
        items = repository.list(
            tenant_id=tenant_id(principal), entity_type=entity_type, owner_user_id=owner, limit=limit, offset=offset,
        )
        return {"ok": True, "entity_type": entity_type, "items": items, "limit": limit, "offset": offset,
                "revision": repository.current_revision(tenant_id=tenant_id(principal))}

    @router.get("/api/runtime/v2/entities/{entity_type}/{entity_id}")
    def get_entity_v2(entity_type: str, entity_id: str, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        if entity_type not in ALLOWED_ENTITY_TYPES:
            raise HTTPException(status_code=404, detail="unknown runtime entity type")
        owner = resolve_owner(principal, subject_user_id)
        try:
            item = repository.get(tenant_id=tenant_id(principal), entity_type=entity_type, entity_id=entity_id, owner_user_id=owner)
        except KeyError:
            raise HTTPException(status_code=404, detail="entity not found")
        return {"ok": True, "item": item}

    @router.post("/api/runtime/v2/entities/{entity_type}")
    def upsert_entity_v2(entity_type: str, req: UnifiedRuntimeEntityUpsert, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        if entity_type not in ALLOWED_ENTITY_TYPES:
            raise HTTPException(status_code=404, detail="unknown runtime entity type")
        owner = resolve_owner(principal, subject_user_id)
        payload = dict(req.payload); payload["id"] = req.id
        try:
            item = repository.upsert(
                tenant_id=tenant_id(principal), entity_type=entity_type, entity_id=req.id, payload=payload,
                owner_user_id=owner, expected_version=req.expected_version, updated_by=principal.user_id or "demo-local",
            )
        except RuntimeVersionConflict as exc:
            raise _conflict(exc)
        return {"ok": True, "item": item, "revision": item.get("_revision", 0)}

    @router.delete("/api/runtime/v2/entities/{entity_type}/{entity_id}")
    def delete_entity_v2(
        entity_type: str, entity_id: str, subject_user_id: str = Query(default=""),
        expected_version: int | None = Query(default=None, ge=1), principal=Depends(current_principal),
    ):
        if entity_type not in ALLOWED_ENTITY_TYPES:
            raise HTTPException(status_code=404, detail="unknown runtime entity type")
        owner = resolve_owner(principal, subject_user_id)
        try:
            deleted = repository.delete(
                tenant_id=tenant_id(principal), entity_type=entity_type, entity_id=entity_id,
                owner_user_id=owner, expected_version=expected_version, updated_by=principal.user_id or "demo-local",
            )
        except RuntimeVersionConflict as exc:
            raise _conflict(exc)
        return {"ok": True, "deleted": deleted, "revision": repository.current_revision(tenant_id=tenant_id(principal))}

    @router.get("/api/runtime/v2/changes")
    def runtime_changes(
        since_revision: int = Query(default=0, ge=0), subject_user_id: str = Query(default=""),
        entity_types: str = Query(default=""), limit: int = Query(default=500, ge=1, le=2000),
        principal=Depends(current_principal),
    ):
        owner = resolve_owner(principal, subject_user_id)
        requested = [x.strip() for x in entity_types.split(",") if x.strip()]
        if any(x not in ALLOWED_ENTITY_TYPES for x in requested):
            raise HTTPException(status_code=400, detail="changes only supports runtime-owned entity types")
        return {"ok": True, **repository.changes(
            tenant_id=tenant_id(principal), since_revision=since_revision, owner_user_id=owner,
            entity_types=requested or list(ALLOWED_ENTITY_TYPES), limit=limit,
        )}

    @router.post("/api/runtime/v2/import")
    def import_runtime_v2(
        req: UnifiedRuntimeImportRequest, subject_user_id: str = Query(default=""),
        confirm_replace: bool = Query(default=False), principal=Depends(current_principal),
    ):
        owner = resolve_owner(principal, subject_user_id)
        imported: dict[str, int] = {}
        for state_key, raw in (req.data or {}).items():
            spec = RUNTIME_STATE_SPECS.get(state_key)
            if not spec:
                continue
            entity_type, shape = spec
            if shape == "singleton":
                current = repository.list_all(tenant_id=tenant_id(principal), entity_type=entity_type, owner_user_id=owner)
                expected = int(current[0].get("_version")) if current else None
                repository.upsert(
                    tenant_id=tenant_id(principal), entity_type=entity_type, entity_id="default",
                    payload={"id": "default", "value": raw}, owner_user_id=owner,
                    expected_version=expected, updated_by=principal.user_id or "demo-local",
                )
                imported[state_key] = 1
                continue
            incoming = raw if isinstance(raw, list) else []
            items = [normalize_item(x, i, entity_type) for i, x in enumerate(incoming)]
            if req.mode == "replace":
                if not confirm_replace:
                    raise HTTPException(status_code=409, detail="replace import requires confirm_replace=true")
                repository.replace(
                    tenant_id=tenant_id(principal), entity_type=entity_type, items=items,
                    owner_user_id=owner, scope_owner_user_id=owner, updated_by=principal.user_id or "demo-local",
                )
            else:
                for item in items:
                    current = None
                    try:
                        current = repository.get(tenant_id=tenant_id(principal), entity_type=entity_type, entity_id=item["id"], owner_user_id=owner)
                    except KeyError:
                        pass
                    repository.upsert(
                        tenant_id=tenant_id(principal), entity_type=entity_type, entity_id=item["id"], payload=item,
                        owner_user_id=owner, expected_version=(int(current.get("_version")) if current else None),
                        updated_by=principal.user_id or "demo-local",
                    )
            imported[state_key] = len(items)
        return {"ok": True, "mode": req.mode, "imported": imported,
                "revision": repository.current_revision(tenant_id=tenant_id(principal))}

    # ---------------- v1 compatibility: read/migrate only ----------------
    @router.get("/api/runtime/v1/state")
    def runtime_state_v1(subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        owner = resolve_owner(principal, subject_user_id)
        data: dict[str, Any] = {}
        for state_key, (entity_type, shape) in RUNTIME_STATE_SPECS.items():
            rows = repository.list_all(tenant_id=tenant_id(principal), entity_type=entity_type, owner_user_id=owner)
            data[state_key] = (rows[0].get("value") if rows else None) if shape == "singleton" else rows
        return {"ok": True, "mode": "api", "schemaVersion": 4, "deprecated": True,
                "tenant_id": tenant_id(principal), "subject_user_id": owner, "data": data}

    @router.get("/api/runtime/v1/entities/{entity_type}")
    def list_entities_v1(entity_type: str, subject_user_id: str = Query(default=""), limit: int = Query(default=500, ge=1, le=1000), principal=Depends(current_principal)):
        if entity_type in CANONICAL_ENTITY_TYPES:
            raise HTTPException(status_code=410, detail="entity moved to canonical workspace API")
        if entity_type not in ALLOWED_ENTITY_TYPES:
            raise HTTPException(status_code=404, detail="unknown runtime entity type")
        owner = resolve_owner(principal, subject_user_id)
        return {"ok": True, "entity_type": entity_type,
                "items": repository.list(tenant_id=tenant_id(principal), entity_type=entity_type, owner_user_id=owner, limit=limit)}

    @router.post("/api/runtime/v1/entities/{entity_type}")
    def upsert_entity_v1(entity_type: str, req: UnifiedRuntimeEntityUpsert, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        if entity_type in CANONICAL_ENTITY_TYPES:
            raise HTTPException(status_code=410, detail="entity moved to canonical workspace API")
        if entity_type not in ALLOWED_ENTITY_TYPES:
            raise HTTPException(status_code=404, detail="unknown runtime entity type")
        return upsert_entity_v2(entity_type, req, subject_user_id, principal)

    @router.delete("/api/runtime/v1/entities/{entity_type}/{entity_id}")
    def delete_entity_v1(entity_type: str, entity_id: str, subject_user_id: str = Query(default=""), expected_version: int | None = Query(default=None), principal=Depends(current_principal)):
        if entity_type in CANONICAL_ENTITY_TYPES:
            raise HTTPException(status_code=410, detail="entity moved to canonical workspace API")
        return delete_entity_v2(entity_type, entity_id, subject_user_id, expected_version, principal)

    @router.put("/api/runtime/v1/collections/{state_key}")
    def replace_collection_v1(state_key: str, req: UnifiedRuntimeCollectionReplace, principal=Depends(current_principal)):
        raise HTTPException(status_code=410, detail="full collection replacement removed in v1.4; use granular services or explicit migration import")

    @router.put("/api/runtime/v1/state/{state_key}")
    def put_state_value_v1(state_key: str, req: UnifiedRuntimeStateValue, subject_user_id: str = Query(default=""), principal=Depends(current_principal)):
        spec = RUNTIME_STATE_SPECS.get(state_key)
        if not spec:
            if state_key in {"artifacts", "evidence", "users", "tasks", "knowledge", "jobRows", "jobImports"}:
                raise HTTPException(status_code=410, detail="business state moved to canonical workspace API")
            raise HTTPException(status_code=404, detail="unknown runtime state key")
        entity_type, shape = spec
        if shape == "collection":
            raise HTTPException(status_code=410, detail="full collection replacement removed in v1.4")
        owner = resolve_owner(principal, subject_user_id)
        current = repository.list_all(tenant_id=tenant_id(principal), entity_type=entity_type, owner_user_id=owner)
        expected = int(current[0].get("_version")) if current else None
        item = repository.upsert(
            tenant_id=tenant_id(principal), entity_type=entity_type, entity_id="default",
            payload={"id": "default", "value": req.value}, owner_user_id=owner,
            expected_version=expected, updated_by=principal.user_id or "demo-local",
        )
        return {"ok": True, "state_key": state_key, "value": req.value, "version": item.get("_version")}

    @router.post("/api/runtime/v1/import")
    def import_runtime_v1(req: UnifiedRuntimeImportRequest, principal=Depends(current_principal)):
        if any(k not in RUNTIME_STATE_SPECS for k in (req.data or {})):
            raise HTTPException(status_code=410, detail="canonical business domains must be imported through workspace migration endpoints")
        return import_runtime_v2(req, "", req.mode == "replace", principal)

    @router.delete("/api/runtime/v1/state")
    def clear_runtime_state_v1(confirm: bool = Query(default=False), principal=Depends(current_principal)):
        if not principal.is_super_admin or not confirm:
            raise HTTPException(status_code=403, detail="super admin and confirm=true required")
        return {"ok": True, "deleted": repository.clear_tenant(tenant_id=tenant_id(principal))}

    return router
