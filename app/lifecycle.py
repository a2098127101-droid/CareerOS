from __future__ import annotations

from typing import Literal

from .models import SessionState
from .workflow_templates import WorkflowStepDefinition, WorkflowTemplate, get_workflow_template

WorkflowStatus = Literal["completed", "current", "available", "locked"]

# Backward-compatible default workflow export used by older tests and integrations.
WORKFLOW: tuple[WorkflowStepDefinition, ...] = get_workflow_template("career_development").steps
WorkflowDefinition = WorkflowStepDefinition


def _completed_steps(state: SessionState, artifact_kinds: set[str] | None = None) -> set[str]:
    artifact_kinds = artifact_kinds or set()
    completed: set[str] = set()
    if state.profile.evidence_text.strip():
        completed.add("self_exploration")
    if state.profile.target_job.strip() or state.profile.target_industry.strip():
        completed.add("career_positioning")
    if state.profile.target_job.strip():
        completed.add("target_role")
    if state.track != "待确认" and state.track_recommendation is not None:
        completed.add("person_job_match")
    elif state.profile.target_job.strip() and (state.profile.skills or state.profile.internships or state.profile.projects or state.profile.evidence_text.strip()):
        completed.add("person_job_match")
    if state.review is not None:
        completed.add("gap_analysis")
    if state.revised_draft.strip():
        completed.add("growth_path")
    if state.document_type == "简历" and (state.draft.strip() or state.revised_draft.strip()):
        completed.add("resume")
    if state.document_type in {"职业规划书", "发展报告", "发展成果", "人才发展报告"} and (state.draft.strip() or state.revised_draft.strip()):
        completed.add("career_report")
    if {"ppt", "presentation"} & artifact_kinds:
        completed.add("ppt")
    if "mock_defense" in artifact_kinds:
        completed.add("mock_defense")
    return completed


def workflow_snapshot(
    state: SessionState,
    artifact_kinds: set[str] | None = None,
    *,
    preset_id: str = "career_development",
    template: WorkflowTemplate | None = None,
) -> dict:
    template = template or get_workflow_template(preset_id)
    completed = _completed_steps(state, artifact_kinds)
    first_open: str | None = None
    items: list[dict] = []
    for step in template.steps:
        if step.step_id in completed:
            status: WorkflowStatus = "completed"
        elif first_open is None:
            status = "current"
            first_open = step.step_id
        else:
            status = "available" if "self_exploration" in completed else "locked"
        items.append({
            "id": step.step_id,
            "index": step.index,
            "label": step.label,
            "description": step.description,
            "required_evidence": step.required_evidence,
            "required_artifact": step.required_artifact,
            "status": status,
        })
    done = sum(1 for x in items if x["status"] == "completed")
    current = next((x for x in items if x["status"] == "current"), items[-1] if items else None)
    return {
        "template_id": template.template_id,
        "preset_id": template.preset_id,
        "completed": done,
        "total": len(items),
        "progress": int(done / max(1, len(items)) * 100),
        "current_step": current,
        "steps": items,
    }
