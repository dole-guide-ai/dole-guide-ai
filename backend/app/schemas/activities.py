"""구직활동을 만들고 보여 주는 요청·응답 스키마입니다.

직접 기록할 때는 날짜와 활동 값을, 추천을 예정 활동으로 넣을 때는 추천 ID만 보냅니다.
응답의 회차 번호는 저장된 값이 아니라 대상기간으로 계산한 값입니다.
"""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, model_validator


class ActivityCategory(StrEnum):
    JOB_SEARCH = "job_search"
    NON_JOB_SEARCH = "non_job_search"


class ActivityCreate(BaseModel):
    """직접 기록하거나, `recommendation_id`로 추천을 예정 활동으로 넣습니다."""

    recommendation_id: str | None = None
    activity_date: date | None = None
    category: ActivityCategory | None = None
    kind: str | None = None
    route: str | None = None
    org_name: str | None = None
    job_title: str | None = None
    hours: float | None = None
    file_ids: list[str] = []

    @model_validator(mode="after")
    def need_date_or_recommendation(self) -> ActivityCreate:
        if self.recommendation_id is None and self.activity_date is None:
            raise ValueError("activity_date 또는 recommendation_id가 필요합니다.")
        return self


class ActivityRead(BaseModel):
    activity_id: str
    activity_date: date
    round: int | None
    category: ActivityCategory
    kind: str
    route: str | None = None
    org_name: str | None = None
    job_title: str | None = None
    hours: float | None = None
    planned: bool
    source: str
    state: str | None = None
    file_ids: list[str] = []
