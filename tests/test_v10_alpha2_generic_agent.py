from __future__ import annotations

from app.agent_service import CareerAgentService
from app.models import SessionState


class _Settings:
    product_preset = "career_development"


def _service() -> CareerAgentService:
    svc = object.__new__(CareerAgentService)
    svc.settings = _Settings()
    return svc


def test_generic_demo_draft_does_not_require_competition_identity():
    svc = _service()
    state = SessionState(session_id="S-GENERIC")
    state.profile.evidence_text = "Completed a customer discovery exercise and summarized findings."
    draft = svc._demo_draft(state, "发展报告")
    assert "Career Development Report Draft" in draft
    assert "赛道" not in draft
    assert "学校｜专业｜年级" not in draft


def test_generic_demo_coach_does_not_force_track_selection():
    svc = _service()
    state = SessionState(session_id="S-GENERIC")
    state.profile.evidence_text = "Completed a real project."
    state.track = "待确认"
    reply = svc._demo_coach(state, "下一步")
    assert "确认赛道" not in reply
    assert "成果物" in reply
