from datetime import date

from app.rules.briefing import (
    build_briefing,
    interval_days,
    md,
    person_lines,
    round_lines,
)
from app.rules.next_action import NextAction
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


def test_briefing_job_registration_suggests_resume_without_next_field():
    lines = build_briefing("job_registration", round_=None, action=NextAction.WRITE_RESUME)
    assert lines[0].startswith("구직등록 단계")
    # 다음에 채울 이력서 칸은 이력서 대화(nodes/resume)만 알립니다. 다른 패널의 "지금 상황"에
    # 넣으면 질문과 무관한 이력서 질문이 답에 붙습니다(골든셋 D8).
    assert not any("다음 칸" in line for line in lines)
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


def test_round_lines_job_search_requirement():
    # 골든셋 P-035·P-053: 4차부터 구직활동 필수, 특강만으로는 안 됨 (ACT-026)
    text = " ".join(round_lines(ROUND | {"required_job_search": 1}))
    assert "구직활동(입사지원·면접 등)이 1건 이상" in text
    assert "다른 활동만으로는 채울 수 없어요" in text


def test_round_lines_explain_not_counted():
    # 골든셋 P-007·P-063(같은 날), P-078·P-120(기간 밖)
    items = [
        {"date": "2026-12-08", "status": "same_day"},
        {"date": "2026-11-03", "status": "out_of_period"},
    ]
    text = " ".join(round_lines(ROUND | {"not_counted": items}))
    assert "12월 8일(화)에는 활동이 2건 이상이라 1건만 인정돼요" in text
    assert "다른 날" in text
    assert "11월 3일(화)에 한 활동은 이번 대상기간" in text


def test_round_lines_online_deadline():
    # 골든셋 P-017·P-018·P-093: 인정일 당일 17시 마감, 지났으면 18시까지 방문 (DUE-092·093)
    before = " ".join(round_lines(ROUND | {"d_day": 0, "now_time": "16:50"}))
    after = " ".join(round_lines(ROUND | {"d_day": 0, "now_time": "17:20"}))
    assert "17시까지" in before and "마감" not in before
    assert "17:20이라 오늘 인터넷 신청 마감(17시)이 지났어요" in after
    # 18시도 지났으면 이미 지난 방문 마감을 안내하지 않음
    late = " ".join(round_lines(ROUND | {"d_day": 0, "now_time": "18:30"}))
    assert "마감이 모두 지났어요" in late and "관할 고용센터에 확인" in late
    assert "18시까지 고용센터에 가서" not in late
    # 출석 회차는 인터넷 신청이 아니므로 마감 안내를 붙이지 않음
    attend = " ".join(round_lines(ROUND | {"attendance_required": True}))
    assert "17시" not in attend


def test_briefing_stage_rules():
    # 골든셋 P-004·P-081: 이직 당시 65세 이상은 센터 방문 신청 (PROC-048)
    senior = " ".join(build_briefing("eligibility_application", round_=None, action=None, age=67))
    assert "관할 고용센터에 방문" in senior
    young = " ".join(build_briefing("eligibility_application", round_=None, action=None, age=58))
    assert "방문" not in young
    # 골든셋 P-095: 대기기간 7일 (DUE-057)
    assert "7일은 대기기간" in young
    # 골든셋 P-016·P-154: 1차 교육 (일반 ACT-020 출석, 60세 이상 ACT-021·022 온라인 가능)
    general = " ".join(
        build_briefing("eligibility_applied", round_=None, action=None, group="general")
    )
    assert "출석해 교육" in general
    older = build_briefing(
        "recognition", round_=ROUND | {"round": 1}, action=None, group="age_60_64"
    )
    assert "1차 교육은 온라인 또는 고용센터에서 들어요." in older
