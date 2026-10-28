"""지금 사용자가 할 일 하나를 절차 단계와 이번 회차 상태로 정합니다. LLM 없음.

대화 답변 끝(done 이벤트)에 실어 보내고, 화면은 이 값으로 바로가기 버튼 등을 띄울 수 있습니다.
값 목록은 골든셋 evals/golden/schema.py NEXT_ACTIONS와 같습니다.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Any

from app.rules import application as application_rules
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
    ATTEND_CENTER = "attend_center"
    VISIT_CENTER_TODAY = "visit_center_today"
    CONTACT_CENTER = "contact_center"


# 인정일 당일 지금 시각의 제출 방식(rules/application.submit_mode) → 할 일
_BY_SUBMIT_MODE = {
    application_rules.SEND: NextAction.SUBMIT_BY_SELF,
    application_rules.ATTEND: NextAction.ATTEND_CENTER,
    application_rules.VISIT_TODAY: NextAction.VISIT_CENTER_TODAY,
    application_rules.CHANGE: NextAction.CONTACT_CENTER,
}


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
    now: datetime | None = None,
) -> NextAction | None:
    """실업인정 단계면 회차 상태와 지금 시각으로 정합니다.

    활동이 모자라면 채우기, 다 채웠으면 인정일 전은 신청서 검토입니다. 인정일 당일은 지금 시각의
    제출 방식(17시 전 인터넷 제출, 17~18시 센터 방문, 18시 뒤 센터 문의, 출석 회차는 출석)을
    따릅니다. 필요 건수를 셀 수 없는 회차(remaining None)는 활동 채우기로 둡니다.
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
    if round_facts.get("d_day") == 0 and now is not None:
        mode = application_rules.submit_mode(
            now,
            date.fromisoformat(round_facts["recognition_date"]),
            bool(round_facts.get("attendance_required")),
        )
        # 마감이 지났거나 출석 회차면 남은 활동보다 오늘 해야 할 일이 먼저입니다.
        if mode != application_rules.SEND:
            return _BY_SUBMIT_MODE[mode]
    remaining = round_facts.get("remaining")
    if remaining is None:
        return NextAction.ADD_ACTIVITY
    if remaining > 0:
        only_job_search = (round_facts.get("remaining_job_search") or 0) >= remaining
        return NextAction.ADD_JOB_SEARCH_ACTIVITY if only_job_search else NextAction.ADD_ACTIVITY
    if round_facts.get("d_day") == 0:
        return NextAction.SUBMIT_BY_SELF
    return NextAction.REVIEW_FORM
