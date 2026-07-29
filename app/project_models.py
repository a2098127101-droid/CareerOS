from __future__ import annotations

from pydantic import BaseModel, Field


class ProjectCreateRequest(BaseModel):
    template_version_id: str = Field(min_length=1, max_length=160)
    name: str = Field(default="", max_length=200)


class ProjectAnswerItem(BaseModel):
    question_id: str = Field(min_length=1, max_length=120)
    answer: object


class ProjectAnswersRequest(BaseModel):
    answers: list[ProjectAnswerItem] = Field(min_length=1, max_length=100)
