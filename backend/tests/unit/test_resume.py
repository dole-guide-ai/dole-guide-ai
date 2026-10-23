from datetime import date

from app.rules.resume import (
    can_save_resume,
    career_months,
    check_resume,
    derive_resume_values,
    next_resume_question,
    normalize_date,
    resume_completeness,
)
from app.schemas.common import FormField
from app.schemas.forms.resume import (
    Career,
    Certification,
    DesiredOccupation,
    Education,
    JobPreferences,
    ResumeData,
)

TODAY = date(2026, 10, 12)
PARK_SEPARATION = date(2026, 9, 21)
CHOI_SEPARATION = date(2026, 9, 30)


def f(value, status="confirmed", source="user_answer", transformed=False) -> FormField:
    return FormField(value=value, status=status, source=source, transformed=transformed)


def complete_resume() -> ResumeData:
    """박진수(합성) 이력서를 꼭 묻는 5개가 다 찬 상태로 만듭니다."""
    return ResumeData(
        resume_title=f("제조 생산직 22년 경력 이력서"),
        education=[
            Education(
                item_id="e1",
                education_level=f("고등학교"),
                graduation_status=f("졸업"),
                school_name=f("OO고등학교"),
                start_date=f("1981-03"),
                end_date=f("1984-02"),
                is_highest_education=f(True),
            )
        ],
        job_preferences=JobPreferences(
            desired_occupations=[
                DesiredOccupation(
                    item_id="o1",
                    occupation=f({"code": None, "name": "생산직", "status": "confirmed"}),
                    experience_type=f("경력"),
                )
            ],
            desired_regions=f([{"code": None, "name": "경기 안성시"}]),
            desired_salary=f({"amount": 2800000, "unit": "monthly", "negotiable": False}),
            employment_contract_type=f("기간의 정함이 없는 근로계약"),
            military_alternative=f("해당 없음"),
        ),
        careers=[
            Career(
                item_id="c1",
                company_name=f("OO산업", "extracted", "doc"),
                start_date=f("2004-03", "extracted", "doc"),
                end_date=f("2026-09", "extracted", "doc"),
                position=f("반장"),
                main_duties=f("프레스 라인 운영"),
                occupation=f({"code": None, "name": "생산직"}),
            )
        ],
        certifications=[Certification(item_id="l1", certificate_name=f("지게차운전기능사"))],
        competencies_status=f(None, "not_applicable"),
    )


def ask(data: ResumeData, branch: str = "E7a", separation: date = PARK_SEPARATION) -> str:
    return next_resume_question(data, entry_branch=branch, separation_date=separation).id


# ── 날짜 표현 (2-1.4) ──


def test_relative_month_is_converted_and_needs_confirm() -> None:
    # resume-001: 기준일 2026-10-12, "작년 3월" → 2025-03, 확인 필요
    result = normalize_date("작년 3월부터", TODAY, PARK_SEPARATION)
    assert (result.value, result.transformed, result.ask) == ("2025-03", True, False)

    data = complete_resume()
    data.careers[0].main_duties = f(
        "신입 안전교육(2025-03~)", "extracted", "user_answer", transformed=True
    )
    assert ask(data) == "resume.value_confirm"
    assert not can_save_resume(data)


def test_age_expression_gives_range_only() -> None:
    # resume-002: 이직 당시 67세·이직일 2026-09-30, "63살" → 2020~2022, 값은 정하지 않음
    result = normalize_date("63살부터", TODAY, CHOI_SEPARATION, age_at_separation=67)
    assert result.value is None and result.ask and result.year_range == (2020, 2022)


def test_exact_vague_and_until_now() -> None:
    assert normalize_date("2004년 3월", TODAY, PARK_SEPARATION).value == "2004-03"
    assert normalize_date("작년 봄", TODAY, PARK_SEPARATION).ask
    assert normalize_date("그만둘 때까지", TODAY, PARK_SEPARATION).value == "2026-09"


# ── 검사 · 완성도 ──


def test_conflict_between_document_and_speech() -> None:
    # resume-003: 서류 2004-03 vs 말 2004-05 → conflict, 확인 질문
    data = complete_resume()
    data.careers[0].start_date = f("2004-05", "conflict")
    issues = check_resume(data, PARK_SEPARATION, TODAY)
    assert ("conflict", "/careers/c1/start_date") in [(i.code, i.path) for i in issues]
    assert ask(data) == "resume.value_confirm"


def test_five_done_but_one_check_cannot_save() -> None:
    # resume-005: 5개 완료 + 확인 필요 1개 → 저장 불가, 질문 value_confirm
    data = complete_resume()
    assert resume_completeness(data).filled == 5 and can_save_resume(data)
    data.competencies.languages = f(["영어 하"], "extracted", transformed=True)
    assert resume_completeness(data).filled == 5
    assert not can_save_resume(data)
    assert ask(data) == "resume.value_confirm"


def test_too_many_regions() -> None:
    # resume-006: 희망 지역 4곳 → 3곳 제한
    data = complete_resume()
    data.job_preferences.desired_regions = f([{"code": None, "name": n} for n in "가나다라"])
    issues = check_resume(data, PARK_SEPARATION, TODAY)
    assert ("too_many", "/job_preferences/desired_regions") in [(i.code, i.path) for i in issues]


def test_no_license_counts_as_done() -> None:
    # resume-008: 자격면허 "없어요" → 해당 없음도 완료
    data = complete_resume()
    data.certifications = []
    assert resume_completeness(data).filled == 4
    data.certifications_status = f(None, "not_applicable")
    assert resume_completeness(data).filled == 5


def test_name_only_occupation_counts_as_done() -> None:
    # resume-010: 직종 후보가 안 맞으면 이름만 저장, 희망조건 완료
    data = complete_resume()
    occ = data.job_preferences.desired_occupations[0]
    occ.occupation = f({"code": None, "name": "프레스 반장", "status": "name_only"})
    assert resume_completeness(data).filled == 5
    occ.occupation = f({"code": None, "name": "프레스", "status": "needs_confirmation"})
    assert resume_completeness(data).filled == 4


def test_period_order_future_and_separation_mismatch() -> None:
    data = complete_resume()
    data.careers[0].start_date = f("2027-01")
    data.careers[0].end_date = f("2026-11")
    codes = {i.code for i in check_resume(data, PARK_SEPARATION, TODAY)}
    assert {"period_order", "future_date", "separation_mismatch"} <= codes


# ── 자동 값 ──


def test_derive_status_highest_education_and_experience() -> None:
    data = complete_resume()
    data.careers[0].employment_status = FormField()
    data.education[0].is_highest_education = FormField()
    data.job_preferences.desired_occupations[0].experience_type = FormField()
    derived = derive_resume_values(data, PARK_SEPARATION)
    assert derived.careers[0].employment_status.value == "퇴직"
    assert derived.education[0].is_highest_education.value is True
    occ = derived.job_preferences.desired_occupations[0]
    # 2004-03 ~ 2026-09, 시작·끝 월 포함 = 22년 7개월. 바꾼 값이라 확인 필요
    assert (occ.experience_years.value, occ.experience_months.value) == (22, 7)
    assert occ.experience_type.transformed
    assert data.careers[0].employment_status.value is None  # 원본은 그대로


# ── 다음 질문 순서 (2-1.3) ──


def test_question_order_from_empty_resume() -> None:
    assert ask(ResumeData()) == "resume.career_new"
    data = complete_resume()
    assert ask(data) == "resume.save_ready"
    data.resume_title = FormField()
    assert ask(data) == "resume.resume_title"


def test_old_resume_asks_careers_since_then() -> None:
    old = Career(
        item_id="c1",
        company_name=f("OO아파트 관리사무소", "extracted", "seed"),
        start_date=f("2010-03", "extracted", "seed"),
        end_date=f("2019-04", "extracted", "seed"),
    )
    question = next_resume_question(
        ResumeData(careers=[old]), entry_branch="E7b", separation_date=CHOI_SEPARATION
    )
    assert question.id == "resume.career_since_old"
    assert question.vars["year"] == 2019


# ── 리뷰 반영: 잘못된 월·값 모양 ──


def test_month_out_of_range_is_asked_again() -> None:
    assert normalize_date("2024년 13월", TODAY, PARK_SEPARATION) == normalize_date(
        "모름", TODAY, PARK_SEPARATION
    )
    assert normalize_date("작년 13월", TODAY, PARK_SEPARATION).value is None
    data = complete_resume()
    data.careers[0].end_date = f("2026-13")  # 직접 쓴 잘못된 월은 기간 계산에서 뺍니다
    assert career_months(data.careers) == 0


def test_wrong_value_shapes_do_not_crash() -> None:
    data = complete_resume()
    data.job_preferences.desired_occupations[0].occupation = f("시설관리")
    data.job_preferences.desired_occupations[0].experience_type = FormField()
    data.job_preferences.desired_regions = f("서울 노원구")
    derive_resume_values(data, PARK_SEPARATION)
    assert "too_many" not in {i.code for i in check_resume(data, PARK_SEPARATION, TODAY)}
    resume_completeness(data)
    assert ask(data) == "resume.wish_experience"


def test_date_field_keeps_original_sentence_and_base_date() -> None:
    """F-11: 작년 3월 → 2025-03은 확인 필요이고, 근거에 원래 문장과 기준일이 남습니다."""
    from datetime import date

    from app.rules.resume import date_field, needs_check, normalize_date

    today = date(2026, 10, 12)
    expr = "작년 3월부터"
    f = date_field(expr, normalize_date(expr, today, date(2026, 9, 30)), today)

    assert f.value == "2025-03"
    assert needs_check(f)
    assert f.evidence is not None
    assert (f.evidence.kind, f.evidence.quote, f.evidence.date) == ("utterance", expr, today)
