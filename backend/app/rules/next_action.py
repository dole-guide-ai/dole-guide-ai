"""지금 사용자가 할 일 하나를 절차 단계와 이번 회차 상태로 정합니다. LLM 없음.

대화 답변 끝(done 이벤트)에 실어 보내고, 화면은 이 값으로 바로가기 버튼 등을 띄울 수 있습니다.
값 목록은 골든셋 evals/golden/schema.py NEXT_ACTIONS와 같습니다.
"""

from enum import StrEnum
from typing import Any

from app.schemas.procedure import Stage


class NextAction(StrEnum):
    WRITE_RESUME = "write_resume"
    COMPLETE_EDUCATION = "complete_education"
    PREPARE_ELIGIBILITY = "prepare_eligibility"
    ENTER_RECOGNITION_DATE = "enter_recognition_date"
    ADD_ACTIVITY = "add_activity"
    ADD_JOB_SEARCH_ACTIVITY = "add_job_search_activity"
    REVIEW_FORM = "review_form"
    SUBMIT_BY_SELF = "submit_by_self"


_BY_STAGE = {
    Stage.JOB_REGISTRATION: NextAction.WRITE_RESUME,
    Stage.EDUCATION: NextAction.COMPLETE_EDUCATION,
    Stage.ELIGIBILITY_APPLICATION: NextAction.PREPARE_ELIGIBILITY,
    Stage.ELIGIBILITY_APPLIED: NextAction.ENTER_RECOGNITION_DATE,
}


def next_action(
    stage: str | None,
    round_facts: dict[str, Any] | None,
    *,
    resume_ready: bool = False,
    education_done: bool | None = None,
) -> NextAction | None:
    """실업인정 단계면 회차 상태로 정합니다.

    활동이 모자라면 채우기, 다 채웠으면 인정일 당일은 제출, 그 전은 신청서 검토입니다.
    단계가 넘어가기 직전도 다음 단계 일을 알려 줍니다(화면 안내 entry.py와 같은 기준):
    이직 뒤 이력서가 저장돼 있으면(resume_ready) 교육, 교육을 이수했으면 수급자격 신청 준비입니다.
    이직 전에 저장한 예전 이력서는 고쳐야 하므로 준비된 것으로 보지 않습니다.
    """
    if stage is None:
        return None
    if stage == Stage.JOB_REGISTRATION and resume_ready:
        return NextAction.COMPLETE_EDUCATION
    if stage == Stage.EDUCATION and education_done:
        return NextAction.PREPARE_ELIGIBILITY
    if stage in _BY_STAGE:
        return _BY_STAGE[Stage(stage)]
    if stage != Stage.RECOGNITION or not round_facts:
        return None
    if round_facts.get("remaining", 0) > 0:
        only_job_search = round_facts.get("remaining_job_search", 0) >= round_facts["remaining"]
        return NextAction.ADD_JOB_SEARCH_ACTIVITY if only_job_search else NextAction.ADD_ACTIVITY
    if round_facts.get("d_day") == 0:
        return NextAction.SUBMIT_BY_SELF
    return NextAction.REVIEW_FORM
