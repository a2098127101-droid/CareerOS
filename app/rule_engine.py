from __future__ import annotations

from .models import TrackInput, TrackRecommendation


def recommend_track(signals: TrackInput) -> TrackRecommendation:
    """Internal heuristic recommendation.

    This is intentionally deterministic. It does not claim to replace official
    competition eligibility rules, which must be loaded separately.
    """
    growth = 50
    employment = 50
    reasons: list[str] = []

    if signals.grade_level <= 2:
        growth += 18
        employment -= 8
        reasons.append("当前年级较低，更适合展示探索、成长与能力形成过程。")
    elif signals.grade_level >= 4:
        employment += 16
        growth -= 6
        reasons.append("当前年级较高，更适合围绕明确岗位与求职竞争力组织材料。")

    clarity_delta = (signals.career_goal_clarity - 3) * 10
    employment += clarity_delta
    growth -= int(clarity_delta * 0.7)
    if signals.career_goal_clarity >= 4:
        reasons.append("职业目标较明确，就业赛道适配度上升。")
    elif signals.career_goal_clarity <= 2:
        reasons.append("职业目标仍处探索阶段，成长赛道适配度上升。")

    experience = min(signals.internship_count * 8 + signals.project_count * 4, 28)
    employment += experience
    growth -= int(experience * 0.3)
    if signals.internship_count > 0 or signals.project_count > 1:
        reasons.append("已有实习或项目证据，可支撑岗位匹配与成果展示。")

    if signals.has_clear_target_job:
        employment += 12
        growth -= 5
        reasons.append("已明确目标岗位，可形成岗位要求—个人证据—行动计划的完整链条。")

    growth = max(0, min(100, growth))
    employment = max(0, min(100, employment))

    if abs(growth - employment) < 10:
        track = "待确认"
        reasons.append("两条赛道适配度接近，建议结合当届官方资格与作品要求人工确认。")
    elif employment > growth:
        track = "就业赛道"
    else:
        track = "成长赛道"

    return TrackRecommendation(
        recommended_track=track,
        growth_score=growth,
        employment_score=employment,
        reasons=reasons[:5],
        caveat="该结果仅为产品内部启发式推荐；最终赛道必须以当届官方规则、参赛资格与学校通知为准。",
    )
