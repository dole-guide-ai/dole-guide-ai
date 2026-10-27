"""모델에 줄 "지금 상황"을 사람 말 문장으로 만듭니다. LLM 없음.

값을 JSON으로만 주면 모델이 단계·회차·이력서 상태를 스스로 해석하다 놓칩니다. 코드가 결론을
문장으로 써 주고 모델은 옮기기만 하면, 답이 흔들리지 않고 지금 할 일을 먼저 제안할 수 있습니다
(민수 설계 실험 1: 사실 문장으로 바꾸자 실행 간 흔들림 8점 → 1점).
"""

from datetime import date
from typing import Any

from app.rules.activity_table import load_rules
from app.rules.application import SEND_DEADLINE_HOUR, VISIT_DEADLINE_HOUR
from app.rules.next_action import NextAction
from app.rules.presubmit import PRESUBMIT_STAGES, visit_to_apply
from app.schemas.forms.resume import ResumeData
from app.schemas.procedure import Stage

WEEKDAYS = "월화수목금토일"
DAYS_PER_WEEK = 7
# 실업신고일부터 구직급여를 주지 않는 대기기간 (DUE-057)
WAITING_DAYS = 7
# 이직 당시 만 65세 이상은 인터넷 사전제출 대신 센터 방문 (PROC-048, 화면 안내 M1과 같은 단계)
BEFORE_FIRST_ROUND = (*PRESUBMIT_STAGES, Stage.ELIGIBILITY_APPLIED)
# 회차 점검의 활동 상태(schemas.rounds.ActivityStatus) 중 인정되지 않은 이유
SAME_DAY = "same_day"
OUT_OF_PERIOD = "out_of_period"
# 1차 교육 방식 (ACT-020 일반: 센터 방문 · ACT-021·022 만 60세 이상·장애인: 온라인 또는 센터)
GENERAL = "general"
FIRST_ROUND_EDUCATION = {
    GENERAL: "1차 실업인정일에는 고용센터에 직접 출석해 교육을 들어야 해요(인터넷 신청 아님).",
    "age_60_64": "1차 교육은 온라인 또는 고용센터에서 들어요.",
    "age65_or_disabled": "1차 교육은 온라인 또는 고용센터에서 들어요.",
}
# 사람 요약에 적는 최근 경력 수
SUMMARY_CAREERS = 2

STAGE_TEXT = {
    Stage.JOB_REGISTRATION: (
        "구직등록 단계예요. 고용24 이력서를 다 써야 다음 단계(수급자격 교육)로 가요."
    ),
    Stage.EDUCATION: "수급자격 신청자 교육(온라인)을 들을 단계예요.",
    Stage.ELIGIBILITY_APPLICATION: "고용센터에 수급자격을 신청할 단계예요.",
    Stage.ELIGIBILITY_APPLIED: "수급자격을 신청했고, 첫 실업인정일을 기다리는 단계예요.",
    Stage.RECOGNITION: (
        "실업인정을 받는 단계예요. 회차마다 재취업활동을 채우고 인정일에 신청해요."
    ),
    Stage.ENDED: "실업급여 받는 기간이 끝났어요.",
}

# 지금 할 일과 그 이유. 사용자가 다른 이야기를 하면 답 끝에 이 할 일을 한 문장으로 제안합니다.
ACTION_TEXT = {
    NextAction.WRITE_RESUME: "이력서 마저 쓰기 (구직등록을 끝내야 교육·수급자격 신청으로 넘어가요)",
    NextAction.COMPLETE_EDUCATION: "수급자격 신청자 교육 듣기 (들어야 수급자격을 신청할 수 있어요)",
    NextAction.PREPARE_ELIGIBILITY: "고용센터 수급자격 신청 준비하기",
    NextAction.ENTER_RECOGNITION_DATE: "고용센터에서 받은 첫 실업인정일 알려 주기 (회차 계산 기준)",
    NextAction.ADD_ACTIVITY: "이번 회차 재취업활동 채우기",
    NextAction.ADD_JOB_SEARCH_ACTIVITY: "이번 회차 구직활동(입사지원·면접 등) 채우기",
    NextAction.REVIEW_FORM: "활동은 다 채웠으니 실업인정 신청서 미리 살펴보기",
    NextAction.SUBMIT_BY_SELF: "오늘이 인정일이라 고용24에서 실업인정 신청하기",
    NextAction.ATTEND_CENTER: "오늘이 출석하는 인정일이라 고용센터에 가서 실업인정 받기",
    NextAction.VISIT_CENTER_TODAY: (
        "인터넷 신청 마감이 지나서 오늘 센터 방문 마감 전에 고용센터에 가서 신청하기"
    ),
    NextAction.CONTACT_CENTER: "오늘 신청 마감이 모두 지나서 다음 절차를 관할 고용센터에 확인하기",
}


def md(day: date) -> str:
    """2026-12-22 → "12월 22일(화)" """
    return f"{day.month}월 {day.day}일({WEEKDAYS[day.weekday()]})"


def interval_days(group: str, round_no: int) -> int | None:
    """N일마다 활동 1건인 회차면 N (반복수급자 14일, 일반 8차부터 7일). 아니면 None."""
    row = next((r for r in load_rules().required.rows if r.matches(group, round_no)), None)
    if row is None:
        return None
    return row.every_days or (DAYS_PER_WEEK if row.weekly_job_search else None)


def round_lines(round_: dict[str, Any]) -> list[str]:
    """회차 계산 결과(round_service.read_current)를 문장으로."""
    n = round_["round"]
    start = date.fromisoformat(round_["period_start"])
    end = date.fromisoformat(round_["period_end"])
    recognition = date.fromisoformat(round_["recognition_date"])
    d_day = round_["d_day"]
    when = "오늘" if d_day == 0 else f"{d_day}일 남음"
    lines = [
        f"이번은 {n}차예요. 활동 대상기간은 {md(start)}부터 {md(end)}까지, "
        f"실업인정일은 {md(recognition)}이에요({when})."
    ]
    if round_.get("required") is None:
        lines.append("이번 회차 필요 활동 수는 여기서 셀 수 없어요. 관할 고용센터 확인이 필요해요.")
    else:
        need = (
            f"필요한 활동은 {round_['required']}건이고 "
            f"지금 인정된 활동은 {round_['counted']}건이에요."
        )
        remaining = round_.get("remaining") or 0
        if remaining:
            job = round_.get("remaining_job_search") or 0
            need += f" {remaining}건 더 해야 해요" + (f"(그중 구직활동 {job}건)." if job else ".")
        else:
            need += " 필요한 건수는 채웠어요."
        lines.append(need)
    job_search = round_.get("required_job_search") or 0
    if job_search and not round_.get("job_search_only"):
        lines.append(
            f"그중 구직활동(입사지원·면접 등)이 {job_search}건 이상 있어야 해요. "
            "취업특강·직업심리검사 같은 다른 활동만으로는 채울 수 없어요."
        )
    if days := round_.get("interval_days"):
        span = f"{days // DAYS_PER_WEEK}주" if days % DAYS_PER_WEEK == 0 else f"{days}일"
        kind = "구직활동" if round_.get("job_search_only") else "활동"
        lines.append(f"이 회차는 {span}마다 {kind}을 1건씩 해야 해요.")
    lines += not_counted_lines(round_.get("not_counted") or [], start, end)
    if round_.get("attendance_required"):
        lines.append(f"{n}차는 고용센터에 직접 출석하는 회차예요.")
    else:
        lines += deadline_lines(d_day, round_.get("now_time"))
    return lines


def not_counted_lines(items: list[dict[str, str]], start: date, end: date) -> list[str]:
    """기록했지만 인정되지 않은 활동의 이유. 같은 날 1건(ACT-110), 대상기간 밖."""
    lines = []
    for item in items:
        day = md(date.fromisoformat(item["date"]))
        if item["status"] == SAME_DAY:
            lines.append(
                f"{day}에는 활동이 2건 이상이라 1건만 인정돼요(같은 날은 1건). "
                "모자란 건수는 다른 날 해야 해요."
            )
        elif item["status"] == OUT_OF_PERIOD:
            lines.append(
                f"{day}에 한 활동은 이번 대상기간({md(start)}~{md(end)}) 밖이라 "
                "이번 회차에 들어가지 않아요."
            )
    return lines


def deadline_lines(d_day: int, now_time: str | None) -> list[str]:
    """인터넷 실업인정 마감(DUE-092·093). 인정일 당일 마감이 지났으면 그 사실을 먼저.

    18시(방문 마감)도 지났으면 이미 지난 마감을 안내하지 않고, 다음 절차는 관할 고용센터에
    확인하라고 합니다(놓친 뒤의 절차는 규칙표에 없음).
    """
    rule = (
        f"실업인정일 당일 인터넷 신청은 0시부터 {SEND_DEADLINE_HOUR}시까지예요. "
        f"{SEND_DEADLINE_HOUR}시까지 못 보내면 그날 {VISIT_DEADLINE_HOUR}시까지 "
        "고용센터에 가서 신청해요."
    )
    hour = int(now_time.split(":")[0]) if d_day == 0 and now_time else None
    if hour is not None and hour >= VISIT_DEADLINE_HOUR:
        return [
            f"지금은 {now_time}이라 오늘 인터넷 신청({SEND_DEADLINE_HOUR}시)과 센터 방문 신청"
            f"({VISIT_DEADLINE_HOUR}시) 마감이 모두 지났어요. "
            "다음 절차는 관할 고용센터에 확인해야 해요.",
        ]
    if hour is not None and hour >= SEND_DEADLINE_HOUR:
        return [
            f"지금은 {now_time}이라 오늘 인터넷 신청 마감({SEND_DEADLINE_HOUR}시)이 지났어요. "
            f"{VISIT_DEADLINE_HOUR}시까지 고용센터에 가서 신청해야 해요.",
            rule,
        ]
    return [rule]


def stage_rule_lines(
    stage: str | None, *, age: int | None, group: str | None, round_no: int | None
) -> list[str]:
    """단계에 따라 미리 알아야 할 규칙: 65세 이상 방문 신청, 대기기간, 1차 교육."""
    lines = []
    if age is not None and visit_to_apply(age, stage):
        lines.append(
            f"이직 당시 만 {age}세라 수급자격 신청은 인터넷 사전제출 대신 "
            "관할 고용센터에 방문해서 해요. 실업급여를 못 받는다는 뜻은 아니에요."
        )
    if stage in BEFORE_FIRST_ROUND:
        lines.append(
            f"수급자격을 신청하면 실업신고일부터 {WAITING_DAYS}일은 대기기간이라 "
            "구직급여가 나오지 않아요."
        )
    if stage == Stage.ELIGIBILITY_APPLIED or round_no == 1:
        lines.append(FIRST_ROUND_EDUCATION.get(group or "", FIRST_ROUND_EDUCATION[GENERAL]))
    return lines


def _val(field: Any) -> Any:
    return getattr(field, "value", None)


def _name(value: Any) -> str:
    """직종·지역처럼 {name: ...}인 값과 글자 값을 같은 모양으로."""
    if isinstance(value, dict):
        return str(value.get("name") or "")
    return "" if value is None else str(value)


def person_lines(
    *,
    age: int,
    separation_date: date,
    group_label: str,
    has_disability: bool,
    resume: ResumeData,
) -> list[str]:
    """이 사람이 누구인지: 나이·이직일·수급자 유형과 이력서에 적힌 경력·희망 조건.

    이름·연락처 같은 기본정보(user_profiles)는 넣지 않습니다. 이력서 칸 값만 씁니다.
    """
    sep = f"{separation_date.year}년 {separation_date.month}월 {separation_date.day}일"
    lines = [
        f"이 사람: 이직 당시 만 {age}세, {sep} 이직, {group_label} 수급자"
        + (", 장애 있음." if has_disability else ".")
    ]
    careers = sorted(resume.careers, key=lambda c: str(_val(c.start_date) or ""), reverse=True)
    if careers:
        parts = []
        for c in careers[:SUMMARY_CAREERS]:
            period = f"{_val(c.start_date) or '?'}~{_val(c.end_date) or '?'}"
            duties = _val(c.main_duties) or "하던 일 아직 비어 있음"
            parts.append(f"{_val(c.company_name) or '회사 이름 없음'}({period}, {duties})")
        more = f" 외 {len(careers) - SUMMARY_CAREERS}곳" if len(careers) > SUMMARY_CAREERS else ""
        lines.append("이력서 경력: " + ", ".join(parts) + more + ".")
    else:
        lines.append("이력서에 아직 경력이 없어요.")
    levels = [_val(e.education_level) for e in resume.education if _val(e.education_level)]
    certs = [_val(c.certificate_name) for c in resume.certifications if _val(c.certificate_name)]
    jobs = [_name(_val(o.occupation)) for o in resume.job_preferences.desired_occupations]
    regions = [_name(r) for r in _val(resume.job_preferences.desired_regions) or []]
    known = [
        f"학력 {levels[0]}" if levels else "",
        f"자격 {', '.join(certs)}" if certs else "",
        f"희망 직종 {', '.join(j for j in jobs if j)}" if any(jobs) else "",
        f"희망 지역 {', '.join(r for r in regions if r)}" if any(regions) else "",
    ]
    if known := [k for k in known if k]:
        lines.append("이력서에 적힌 것: " + " · ".join(known) + ".")
    return lines


def resume_items(resume: ResumeData) -> dict[str, list[dict[str, Any]]]:
    """반복 항목의 item_id와 알아볼 이름. 읽기 모델이 기존 항목 칸을 고칠 때
    씁니다."""
    return {
        "careers": [
            {"item_id": c.item_id, "company": _val(c.company_name)} for c in resume.careers
        ],
        "education": [
            {"item_id": e.item_id, "level": _val(e.education_level)} for e in resume.education
        ],
        "certifications": [
            {"item_id": c.item_id, "name": _val(c.certificate_name)} for c in resume.certifications
        ],
        "desired_occupations": [
            {"item_id": o.item_id, "name": _name(_val(o.occupation))}
            for o in resume.job_preferences.desired_occupations
        ],
    }


def build_briefing(
    stage: str | None,
    *,
    round_: dict[str, Any] | None,
    action: NextAction | None,
    education_done: bool | None = None,
    person: list[str] | None = None,
    age: int | None = None,
    group: str | None = None,
) -> list[str]:
    """모델 입력 맨 앞에 둘 "지금 상황" 문장들. 사람 요약(person_lines)이 맨 앞에 옵니다."""
    lines: list[str] = list(person or [])
    if stage in STAGE_TEXT:
        lines.append(STAGE_TEXT[Stage(stage)])
    if stage == Stage.EDUCATION and education_done is False:
        lines.append("수급자격 신청자 교육을 아직 듣지 않았어요.")
    round_no = round_["round"] if round_ else None
    lines += stage_rule_lines(stage, age=age, group=group, round_no=round_no)
    if round_:
        lines += round_lines(round_)
    if action:
        lines.append(f"지금 할 일: {ACTION_TEXT[action]}")
    return lines
