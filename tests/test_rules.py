from app.models import TrackInput
from app.rule_engine import recommend_track


def test_low_grade_unclear_goal_favors_growth():
    r = recommend_track(TrackInput(grade_level=1, career_goal_clarity=1, internship_count=0, project_count=0, has_clear_target_job=False))
    assert r.growth_score > r.employment_score
    assert r.recommended_track == "成长赛道"


def test_senior_clear_goal_with_experience_favors_employment():
    r = recommend_track(TrackInput(grade_level=4, career_goal_clarity=5, internship_count=2, project_count=2, has_clear_target_job=True))
    assert r.employment_score > r.growth_score
    assert r.recommended_track == "就业赛道"
