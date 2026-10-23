"""계정에 들어왔을 때 첫 화면을 정하는 진입 분기 서비스입니다.

절차 단계, 이력서 상태, 지금 회차와 D-day를 보고 어떤 패널을 열지, 진행바를 어디까지 채울지,
제목을 무엇으로 할지 정합니다.
지금은 분기와 패널만 정하는 최소판이고, 첫 안내 문구 템플릿과 덧붙임 규칙은 이후에 채웁니다.
"""

from enum import StrEnum

from app.schemas.accounts import Entry, EntryFlags, EntryUi, Progress
from app.schemas.procedure import ProcedureRead, Stage
from app.schemas.rounds import RoundSummary


class ResumeState(StrEnum):
    """진입 분기에서 보는 이력서 상태 (이력서가 없으면 None)."""

    DRAFT = "draft"  # 고치는 중
    OUTDATED = "outdated"  # 저장했지만 퇴사일 이전 이력서
    READY = "ready"  # 퇴사 뒤에 저장함


_STAGE_STEP = {
    Stage.JOB_REGISTRATION: 1,
    Stage.EDUCATION: 2,
    Stage.ELIGIBILITY_APPLICATION: 3,
    Stage.ELIGIBILITY_APPLIED: 3,
    Stage.RECOGNITION: 4,
    Stage.ENDED: 4,
}
_PANEL = {
    "E1": "B",
    "E3": "B",
    "E4a": "B",
    "E4b": "B",
    "E5a": "Q",
    "E5b": "B",
    "E6": "E",
    "E7a": "A",
    "E7b": "A",
    "E7c": "A",
    "END": "B",
}
_TITLE = {
    1: "이력서부터 같이 만들어요",
    2: "온라인 교육을 들어요",
    3: "수급자격 신청을 준비해요",
    4: "이번 회차 할 일",
}


def branch_id(
    procedure: ProcedureRead,
    resume_status: ResumeState | None,
    round_: RoundSummary | None,
    d_day: int | None,
) -> str:
    if procedure.recipient_group == "repeat":
        return "E1"
    stage = procedure.stage
    if stage == Stage.ENDED:
        return "END"
    if stage == Stage.RECOGNITION:
        # 실업인정 단계인데 오늘이 속한 회차가 없으면 마지막 회차가 지난 것이라 종료로 봅니다.
        if round_ is None or d_day is None:
            return "END"
        if d_day == 0:
            return "E3"
        return "E4a" if round_.round == 1 else "E4b"
    if stage == Stage.ELIGIBILITY_APPLIED:
        return "E5b"
    if stage == Stage.ELIGIBILITY_APPLICATION:
        return "E5a"
    if stage == Stage.EDUCATION or resume_status == ResumeState.READY:
        return "E6"
    if resume_status == ResumeState.DRAFT:
        return "E7c"
    return "E7b" if resume_status == ResumeState.OUTDATED else "E7a"


def build_entry(
    procedure: ProcedureRead,
    resume_status: ResumeState | None,
    round_: RoundSummary | None,
    d_day: int | None,
) -> Entry:
    branch = branch_id(procedure, resume_status, round_, d_day)
    step = _STAGE_STEP[procedure.stage]
    if branch == "E6":
        step = 2
    next_text = (
        f"다음 기한 : {round_.round}차 실업인정일 {round_.recognition_date:%m.%d}"
        if round_ and step == 4
        else ""
    )
    return Entry(
        branch_id=branch,
        panel=_PANEL[branch],
        progress=Progress(current=step, done=list(range(1, step))),
        title=_TITLE[step],
        next_step_text=next_text,
        ui=EntryUi(big_text=procedure.age_at_separation >= 65),
        flags=EntryFlags(m1=procedure.age_at_separation >= 65 and step <= 3),
    )
