from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactTemplate:
    template_id: str
    kind: str
    label: str
    aliases: tuple[str, ...]
    renderer: str
    review_rubric: str
    presets: tuple[str, ...]


ARTIFACT_TEMPLATES: tuple[ArtifactTemplate, ...] = (
    ArtifactTemplate("resume_v1", "resume", "履历 / 简历", ("简历", "履历", "resume"), "structured_text", "resume_general_v1",
                     ("career_development", "campus_career", "career_service", "career_competition")),
    ArtifactTemplate("career_report_v1", "career_report", "职业发展报告", ("发展报告", "职业规划书", "职业发展报告", "career_report"),
                     "longform_report", "career_report_general_v1", ("career_development", "campus_career", "career_service", "career_competition")),
    ArtifactTemplate("action_plan_v1", "action_plan", "行动计划", ("行动计划", "成长计划", "发展计划", "action_plan"),
                     "structured_plan", "action_plan_general_v1", ("career_development", "campus_career", "career_service", "enterprise_talent")),
    ArtifactTemplate("portfolio_v1", "portfolio", "作品集", ("作品集", "portfolio"), "portfolio", "portfolio_general_v1",
                     ("career_development", "campus_career", "career_service")),
    ArtifactTemplate("assessment_v1", "assessment", "能力评估", ("能力评估", "人才评估", "assessment"), "structured_report", "assessment_general_v1",
                     ("enterprise_talent", "career_service")),
    ArtifactTemplate("development_report_v1", "development_report", "人才发展成果", ("发展成果", "人才发展报告", "development_report"),
                     "longform_report", "talent_development_v1", ("enterprise_talent",)),
    ArtifactTemplate("presentation_v1", "presentation", "展示材料", ("展示材料", "PPT", "presentation"), "slide_outline", "presentation_general_v1",
                     ("career_development", "campus_career", "career_competition", "enterprise_talent")),
    ArtifactTemplate("mock_defense_v1", "mock_defense", "模拟训练", ("模拟训练", "模拟面试", "模拟答辩", "mock_defense"),
                     "interactive_session", "mock_session_general_v1", ("career_development", "campus_career", "career_service", "career_competition", "enterprise_talent")),
)


def list_artifact_templates(preset_id: str | None = None) -> list[dict]:
    preset = (preset_id or "").strip()
    out = []
    for item in ARTIFACT_TEMPLATES:
        if preset and preset not in item.presets:
            continue
        out.append({
            "template_id": item.template_id,
            "kind": item.kind,
            "label": item.label,
            "aliases": list(item.aliases),
            "renderer": item.renderer,
            "review_rubric": item.review_rubric,
            "presets": list(item.presets),
        })
    return out


def resolve_artifact_template(document_type: str | None, preset_id: str | None = None) -> ArtifactTemplate:
    value = (document_type or "").strip().lower()
    preset = (preset_id or "career_development").strip()
    for item in ARTIFACT_TEMPLATES:
        aliases = {a.lower() for a in item.aliases} | {item.kind.lower(), item.template_id.lower(), item.label.lower()}
        if value in aliases and (preset in item.presets or not preset):
            return item
    # Safe generic fallback: enterprise defaults to development report; other presets to career report.
    fallback_kind = "development_report" if preset == "enterprise_talent" else "career_report"
    return next(x for x in ARTIFACT_TEMPLATES if x.kind == fallback_kind)


def artifact_template_from_record(record: dict) -> ArtifactTemplate:
    return ArtifactTemplate(
        template_id=str(record.get("template_id") or "custom_artifact"),
        kind=str(record.get("kind") or "custom_artifact"),
        label=str(record.get("label") or record.get("kind") or "Custom Artifact"),
        aliases=tuple(str(x) for x in (record.get("aliases") or [])),
        renderer=str(record.get("renderer") or "structured_text"),
        review_rubric=str(record.get("review_rubric") or "general_v1"),
        presets=tuple(str(x) for x in (record.get("presets") or [])),
    )
