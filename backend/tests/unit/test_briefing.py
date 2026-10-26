from datetime import date

from app.rules.briefing import (
    build_briefing,
    interval_days,
    md,
    person_lines,
    resume_line,
    round_lines,
)
from app.rules.next_action import NextAction
from app.rules.resume import ResumeQuestion
from app.schemas.forms.resume import ResumeData

ROUND = {
    "round": 3,
    "period_start": "2026-11-25",
    "period_end": "2026-12-22",
    "recognition_date": "2026-12-22",
    "d_day": 5,
    "required": 2,
    "counted": 1,
    "remaining": 1,
    "remaining_job_search": 1,
    "attendance_required": False,
}


def test_md_has_weekday():
    assert md(date(2026, 12, 22)) == "12월 22일(화)"


def test_round_lines_state_counts_and_dates():
    lines = round_lines(ROUND)
    assert "3차" in lines[0] and "12월 22일(화)" in lines[0] and "5일 남음" in lines[0]
    assert "필요한 활동은 2건" in lines[1] and "1건 더 해야 해요(그중 구직활동 1건)" in lines[1]


def test_round_lines_when_count_unknown():
    lines = round_lines(ROUND | {"required": None, "d_day": 0})
    assert "오늘" in lines[0]
    assert "고용센터 확인" in lines[1]


def test_round_lines_satisfied_and_attendance():
    lines = round_lines(ROUND | {"counted": 2, "remaining": 0, "attendance_required": True})
    assert "채웠어요" in lines[1]
    assert "출석" in lines[2]


def test_resume_line_uses_question_template():
    line = resume_line(ResumeQuestion("resume.career_duties", {"company": "한빛물류"}))
    assert line is not None and "한빛물류에서는 주로 어떤 일을 하셨어요?" in line


def test_resume_line_missing_var_and_unknown_id():
    assert "{" not in (resume_line(ResumeQuestion("resume.career_duties")) or "")
    # 바꾼 값 확인은 대화에서 묻지 않으므로 템플릿이 없습니다.
    assert resume_line(ResumeQuestion("resume.value_confirm")) is None
    assert resume_line(None) is None


def test_briefing_job_registration_suggests_resume():
    lines = build_briefing(
        "job_registration",
        round_=None,
        action=NextAction.WRITE_RESUME,
        resume_question=ResumeQuestion("resume.license"),
    )
    assert lines[0].startswith("구직등록 단계")
    assert any("자격증" in line for line in lines)
    assert lines[-1].startswith("지금 할 일: 이력서")


def test_briefing_recognition_round_then_action():
    lines = build_briefing("recognition", round_=ROUND, action=NextAction.ADD_JOB_SEARCH_ACTIVITY)
    assert any("1건 더" in line for line in lines)
    assert lines[-1] == "지금 할 일: 이번 회차 구직활동(입사지원·면접 등) 채우기"


def test_person_lines_summarize_who_and_resume():
    data = ResumeData.model_validate(
        {
            "careers": [
                {
                    "item_id": "c1",
                    "company_name": {"value": "한빛물류"},
                    "start_date": {"value": "2012-03"},
                    "end_date": {"value": "2026-09"},
                    "main_duties": {"value": "입출고 관리"},
                }
            ],
            "certifications": [
                {"item_id": "q1", "certificate_name": {"value": "지게차운전기능사"}}
            ],
            "job_preferences": {"desired_regions": {"value": [{"code": None, "name": "인천"}]}},
        }
    )
    lines = person_lines(
        age=61,
        separation_date=date(2026, 9, 30),
        group_label="일반",
        has_disability=False,
        resume=data,
    )

    assert lines[0] == "이 사람: 이직 당시 만 61세, 2026년 9월 30일 이직, 일반 수급자."
    assert lines[1] == "이력서 경력: 한빛물류(2012-03~2026-09, 입출고 관리)."
    assert lines[2] == "이력서에 적힌 것: 자격 지게차운전기능사 · 희망 지역 인천."


def test_person_lines_without_career():
    lines = person_lines(
        age=67,
        separation_date=date(2026, 9, 30),
        group_label="만 65세 이상",
        has_disability=True,
        resume=ResumeData(),
    )
    assert lines[0].endswith("장애 있음.")
    assert lines[1] == "이력서에 아직 경력이 없어요."


def test_interval_days_from_rules_table():
    assert interval_days("repeat", 3) == 14
    assert interval_days("general", 8) == 7
    assert interval_days("general", 4) is None


def test_round_lines_state_interval_rule():
    lines = round_lines(ROUND | {"interval_days": 14, "job_search_only": True})
    assert "이 회차는 2주마다 구직활동을 1건씩 해야 해요." in lines
