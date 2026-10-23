"""계정에 들어왔을 때 첫 화면을 정하는 진입 분기 서비스입니다.

절차 단계, 이력서 상태, 지금 회차와 D-day를 보고 어떤 패널을 열지, 진행바를 어디까지 채울지,
제목을 무엇으로 할지 정합니다.
지금은 분기와 패널, 마지막 회차·수급 종료 안내(F-33)만 정하고,
첫 안내 문구 템플릿과 덧붙임 규칙은 이후에 채웁니다.
"""

from app.schemas.accounts import Entry, EntryFlags, EntryMessage, EntryUi, Progress
from app.schemas.procedure import ProcedureRead, Stage
from app.schemas.rounds import RoundSummary

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
# 이직 당시 만 65세 이상이면 글자 크게를 기본으로 켭니다 (1장 1.6 M4, F-06).
BIG_TEXT_AGE = 65

_TITLE = {
    1: "이력서부터 같이 만들어요",
    2: "온라인 교육을 들어요",
    3: "수급자격 신청을 준비해요",
    4: "이번 회차 할 일",
}
END_TITLE = "실업급여 수급이 끝났어요"

# 마지막 회차·종료 안내 (F-33, 설계 6.6). 종료 사유별 문장은 종료 화면 첫 안내에 씁니다.
LAST_ROUND_TEXT = "이번이 마지막 회차예요. 이번 실업인정을 받으면 실업급여 수급이 끝나요."
_END_TEXT = {
    "exhausted": "소정급여일수를 모두 받아 실업급여 수급이 끝났어요.",
    "period_expired": "수급기간(그만둔 다음 날부터 12개월)이 지나 실업급여 수급이 끝났어요.",
    "employed": "취업해서 실업급여 수급이 끝났어요. 다시 일을 시작하신 걸 축하드려요.",
}
_END_DEFAULT = "실업급여 수급이 끝났어요."
# 실업인정 단계인데 남은 회차가 없음(마지막 인정일 뒤, 종료 처리 전). 종료로 확정해 말하지 않습니다.
NO_ROUND_TEXT = (
    "남은 실업인정 회차가 없어요. 수급이 끝나는지와 다음 할 일은 관할 고용센터에 확인해 주세요."
)


def branch_id(
    procedure: ProcedureRead,
    resume_status: str | None,
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
    if stage == Stage.EDUCATION or resume_status == "ready":
        return "E6"
    if resume_status == "draft":
        return "E7c"
    return "E7b" if resume_status == "outdated" else "E7a"


def build_entry(
    procedure: ProcedureRead,
    resume_status: str | None,
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
    title = _TITLE[step]
    messages: list[EntryMessage] = []
    end = procedure.expected_end_date
    if branch == "END" and procedure.stage == Stage.ENDED:
        title = END_TITLE
        next_text = f"수급 종료 : {end:%m.%d}" if end else ""
        text = _END_TEXT.get(procedure.end_reason or "", _END_DEFAULT)
        messages.append(EntryMessage(template_id="T-END", text=text))
    elif branch == "END":
        # 종료 처리(`_close_if_ended`) 전이라 끝났다고 확정하지 않고 예정일과 확인 안내만 줍니다.
        next_text = f"수급 종료 예정 : {end:%m.%d}" if end else ""
        messages.append(EntryMessage(template_id="T-NO-ROUND", text=NO_ROUND_TEXT))
    elif round_ and procedure.last_round and round_.round == procedure.last_round:
        messages.append(EntryMessage(template_id="T-LAST", text=LAST_ROUND_TEXT))
    return Entry(
        branch_id=branch,
        panel=_PANEL[branch],
        progress=Progress(current=step, done=list(range(1, step))),
        title=title,
        next_step_text=next_text,
        messages=messages,
        ui=EntryUi(big_text=procedure.age_at_separation >= BIG_TEXT_AGE),
        flags=EntryFlags(m1=procedure.age_at_separation >= 65 and step <= 3),
    )
