from __future__ import annotations

from contextvars import ContextVar


_tenant_id: ContextVar[str] = ContextVar("careeros_tenant_id", default="")
_platform_admin: ContextVar[bool] = ContextVar("careeros_platform_admin", default=False)


def set_tenant_context(tenant_id: str, *, platform_admin: bool = False) -> None:
    _tenant_id.set((tenant_id or "").strip())
    _platform_admin.set(bool(platform_admin))


def clear_tenant_context() -> None:
    _tenant_id.set("")
    _platform_admin.set(False)


def current_tenant_id() -> str:
    return _tenant_id.get()


def platform_admin_context() -> bool:
    return _platform_admin.get()
