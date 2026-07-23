from __future__ import annotations

from .auth_store import AuthStore, Principal
from .domain.roles import canonical_role
from .models import SessionState


class AuthorizationError(PermissionError):
    pass


def can_access_session(principal: Principal, state: SessionState, auth_store: AuthStore, *, write: bool = False) -> bool:
    if principal.is_super_admin:
        return True
    if principal.tenant_id != state.tenant_id:
        return False
    role = canonical_role(principal.role)
    if role == "organization_admin":
        return True
    if role == "participant":
        return bool(state.student_user_id) and state.student_user_id == principal.user_id
    if role == "advisor":
        group_ids = auth_store.user_group_ids(principal.user_id, principal.tenant_id, role="advisor")
        return bool(state.class_id and state.class_id in group_ids)
    return False


def require_session_access(principal: Principal, state: SessionState, auth_store: AuthStore, *, write: bool = False) -> None:
    if not can_access_session(principal, state, auth_store, write=write):
        raise AuthorizationError("session access denied")


def can_manage_tenant(principal: Principal, tenant_id: str) -> bool:
    return principal.is_super_admin or (principal.is_organization_admin and principal.tenant_id == tenant_id)
