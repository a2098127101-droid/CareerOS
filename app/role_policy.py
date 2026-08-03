from __future__ import annotations

from dataclasses import dataclass

from .domain.roles import canonical_role

ROLE_LEVEL = {
    "participant": 10,
    "advisor": 20,
    "organization_admin": 30,
    "platform_admin": 40,
}


@dataclass(frozen=True)
class RoleDecision:
    allowed: bool
    reason: str


class RolePolicy:
    """Single source of truth for identity mutations across Workspace/Admin APIs."""

    @staticmethod
    def normalize(role: str) -> str:
        value = canonical_role(role)
        if value not in ROLE_LEVEL:
            raise ValueError("invalid role")
        return value

    def can_create_role(self, actor_role: str, target_role: str, *, is_super_admin: bool = False) -> RoleDecision:
        actor = "platform_admin" if is_super_admin else self.normalize(actor_role)
        target = self.normalize(target_role)
        if actor == "platform_admin":
            return RoleDecision(True, "platform admin may create any role")
        if actor == "organization_admin":
            return RoleDecision(target in {"participant", "advisor"}, "organization admin may create participant or advisor only")
        if actor == "advisor":
            return RoleDecision(target == "participant", "advisor may invite participant only")
        return RoleDecision(False, "participant cannot create users")

    def can_disable(self, actor_role: str, target_role: str, *, is_super_admin: bool = False, self_target: bool = False) -> RoleDecision:
        actor = "platform_admin" if is_super_admin else self.normalize(actor_role)
        target = self.normalize(target_role)
        if self_target:
            return RoleDecision(False, "self-disable must use the account lifecycle workflow")
        if actor == "platform_admin":
            return RoleDecision(True, "platform admin may disable lower-scope accounts")
        if actor == "organization_admin":
            return RoleDecision(target in {"participant", "advisor"}, "organization admin may disable participant/advisor only")
        if actor == "advisor":
            return RoleDecision(target == "participant", "advisor may disable assigned participant only")
        return RoleDecision(False, "participant cannot disable users")
