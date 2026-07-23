from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DomainProfile:
    profile_id: str
    product_name: str
    product_subtitle: str
    organization_label: str
    advisor_label: str
    member_label: str
    cohort_label: str
    artifact_label: str
    features: frozenset[str] = field(default_factory=frozenset)

    @property
    def enable_competition_template(self) -> bool:
        return "competition_template" in self.features

    @property
    def enable_school_features(self) -> bool:
        """Backward-compatible alias; new code should use capability flags."""
        return "campus_features" in self.features

    def has(self, capability: str) -> bool:
        return capability in self.features


PROFILES: dict[str, DomainProfile] = {
    "career_development": DomainProfile(
        profile_id="career_development",
        product_name="CareerOS",
        product_subtitle="AI Career Development Operating System",
        organization_label="组织",
        advisor_label="顾问",
        member_label="用户",
        cohort_label="分组",
        artifact_label="成果物",
        features=frozenset({"group_management", "advisor_workspace", "job_intelligence", "artifact_workspace"}),
    ),
    "campus_career": DomainProfile(
        profile_id="campus_career",
        product_name="CareerOS Campus",
        product_subtitle="AI Career Education Workspace",
        organization_label="学校",
        advisor_label="教师",
        member_label="学生",
        cohort_label="班级",
        artifact_label="作品",
        features=frozenset({"campus_features", "group_management", "advisor_workspace", "job_intelligence", "artifact_workspace"}),
    ),
    "career_competition": DomainProfile(
        profile_id="career_competition",
        product_name="CareerOS Competition",
        product_subtitle="AI Career Competition Workspace",
        organization_label="组织",
        advisor_label="指导者",
        member_label="参与者",
        cohort_label="分组",
        artifact_label="参赛成果",
        features=frozenset({"competition_template", "group_management", "advisor_workspace", "job_intelligence", "artifact_workspace"}),
    ),
    "career_service": DomainProfile(
        profile_id="career_service",
        product_name="CareerOS Service",
        product_subtitle="AI Career Service Platform",
        organization_label="机构",
        advisor_label="顾问",
        member_label="客户",
        cohort_label="项目组",
        artifact_label="成果物",
        features=frozenset({"group_management", "advisor_workspace", "job_intelligence", "artifact_workspace"}),
    ),
    "enterprise_talent": DomainProfile(
        profile_id="enterprise_talent",
        product_name="CareerOS Talent",
        product_subtitle="AI Talent Development & Internal Mobility Workspace",
        organization_label="企业",
        advisor_label="导师 / HR",
        member_label="员工",
        cohort_label="人才组",
        artifact_label="发展成果",
        features=frozenset({"group_management", "advisor_workspace", "talent_assessment", "internal_mobility", "artifact_workspace"}),
    ),
}


def get_domain_profile(profile_id: str) -> DomainProfile:
    return PROFILES.get((profile_id or "").strip(), PROFILES["career_development"])
