from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ParticipantProfile(BaseModel):
    """Canonical cross-industry participant profile.

    Vertical presets may place domain-specific fields in custom_attributes instead of expanding
    the platform core model for every industry.
    """

    display_name: str = ""
    organization_context: str = ""
    background: str = ""
    education: list[str] = Field(default_factory=list)
    experience: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    target_opportunity: str = ""
    target_industry: str = ""
    target_locations: list[str] = Field(default_factory=list)
    compensation_expectation: str = ""
    goals: list[str] = Field(default_factory=list)
    evidence_text: str = ""
    custom_attributes: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_legacy(cls, profile: Any) -> "ParticipantProfile":
        data = profile.model_dump() if hasattr(profile, "model_dump") else dict(profile or {})
        education_parts = [x for x in [data.get("degree", ""), data.get("school", ""), data.get("major", ""), data.get("grade", "")] if x]
        experience = list(data.get("internships") or [])
        goals = [x for x in [data.get("competition_goal", "")] if x]
        custom = {
            "school": data.get("school", ""),
            "major": data.get("major", ""),
            "grade": data.get("grade", ""),
            "degree": data.get("degree", ""),
        }
        return cls(
            display_name=data.get("name", ""),
            organization_context=data.get("school", ""),
            background=data.get("major", ""),
            education=education_parts,
            experience=experience,
            interests=list(data.get("interests") or []),
            skills=list(data.get("skills") or []),
            projects=list(data.get("projects") or []),
            target_opportunity=data.get("target_job", ""),
            target_industry=data.get("target_industry", ""),
            target_locations=list(data.get("target_cities") or []),
            compensation_expectation=data.get("expected_salary", ""),
            goals=goals,
            evidence_text=data.get("evidence_text", ""),
            custom_attributes=custom,
        )
