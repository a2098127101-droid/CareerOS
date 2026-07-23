from __future__ import annotations

CANONICAL_ROLES = {"platform_admin", "organization_admin", "advisor", "participant"}
LEGACY_ROLES = {"super_admin", "school_admin", "teacher", "student"}

LEGACY_TO_CANONICAL = {
    "super_admin": "platform_admin",
    "school_admin": "organization_admin",
    "teacher": "advisor",
    "student": "participant",
}
CANONICAL_TO_LEGACY = {v: k for k, v in LEGACY_TO_CANONICAL.items()}


def canonical_role(role: str) -> str:
    value = (role or "").strip()
    return LEGACY_TO_CANONICAL.get(value, value)


def storage_role(role: str) -> str:
    """Map canonical API roles to legacy storage roles during compatibility migration."""
    value = canonical_role(role)
    return CANONICAL_TO_LEGACY.get(value, role)


def role_matches(actual: str, expected: str) -> bool:
    return canonical_role(actual) == canonical_role(expected)


def any_role_matches(actual: str, expected_roles: set[str] | tuple[str, ...] | list[str]) -> bool:
    actual_c = canonical_role(actual)
    return any(actual_c == canonical_role(x) for x in expected_roles)
