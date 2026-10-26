"""이력서 사실 → 칸 쓰기 (rules/resume_facts.py). 기준일 2026-10-12, 퇴사일 2026-09-30."""

from datetime import date

from app.rules.resume import normalize_date
from app.rules.resume_facts import (
    CareerFact,
    CertificationFact,
    EducationFact,
    ResumeFacts,
    plan_writes,
)
from app.schemas.forms.resume import Career, ResumeData

TODAY = date(2026, 10, 12)
SEPARATION = date(2026, 9, 30)


def _plan(facts: ResumeFacts, data: ResumeData | None = None):
    return plan_writes(data or ResumeData(), facts, TODAY, SEPARATION)


def _values(plan) -> dict:
    return {w.path: w.value for w in plan.writes}


def test_relative_and_spoken_dates_become_year_month() -> None:
    plan = _plan(ResumeFacts(careers=[CareerFact(start="작년 삼월", end="올 구월")]))

    assert _values(plan) == {"/careers/c1/start_date": "2025-03", "/careers/c1/end_date": "2026-09"}
    assert all(w.transformed for w in plan.writes)  # 바꾼 값은 확인 필요


def test_vague_start_asks_and_creates_no_empty_career() -> None:
    plan = _plan(ResumeFacts(careers=[CareerFact(start="재작년 겨울")]))

    assert plan.writes == []
    assert plan.asks


def test_duties_without_company_go_to_last_career() -> None:
    data = ResumeData(careers=[Career(item_id="c7")])

    plan = _plan(ResumeFacts(careers=[CareerFact(position="반장")]), data)

    assert _values(plan) == {"/careers/c7/position": "반장"}


def test_same_company_updates_existing_item() -> None:
    data = ResumeData.model_validate(
        {"careers": [{"item_id": "c1", "company_name": {"value": "(주)OO산업"}}]}
    )

    plan = _plan(ResumeFacts(careers=[CareerFact(company_name="OO산업", start="2004년 4월")]), data)

    assert "/careers/c1/start_date" in _values(plan)


def test_graduation_year_only_defaults_to_february_for_confirmation() -> None:
    fact = EducationFact(school_name="OO고등학교", education_level="고등학교", end="1990년")

    plan = _plan(ResumeFacts(education=[fact]))

    assert _values(plan)["/education/e1/end_date"] == "1990-02"
    end = next(w for w in plan.writes if w.path.endswith("end_date"))
    assert end.transformed and "2월" in end.evidence["note"]


def test_certification_year_and_preferences() -> None:
    facts = ResumeFacts(
        certifications=[CertificationFact(certificate_name="지게차운전기능사", acquired="2011년")],
        desired_occupations=["생산직"],
        desired_regions=["경기 화성"],
    )

    values = _values(_plan(facts))

    assert values["/certifications/q1/acquired_date"] == "2011"
    assert values["/job_preferences/desired_occupations/o1/occupation"]["name"] == "생산직"
    assert values["/job_preferences/desired_regions"] == [{"code": None, "name": "경기 화성"}]


def test_spoken_month_and_short_year_word() -> None:
    assert normalize_date("올 구월", TODAY, SEPARATION).value == "2026-09"
    assert normalize_date("올렸어요", TODAY, SEPARATION).value is None


def test_occupation_and_position_go_to_separate_fields() -> None:
    fact = CareerFact(company_name="대성기계", occupation="생산직", position="반장")

    values = _values(_plan(ResumeFacts(careers=[fact])))

    assert values["/careers/c1/position"] == "반장"
    assert values["/careers/c1/occupation"]["name"] == "생산직"


def test_occupation_in_position_moves_to_occupation_and_short_duties_ask() -> None:
    facts = ResumeFacts(
        careers=[CareerFact(company_name="한빛물류", position="생산직", main_duties="포장")]
    )
    plan = plan_writes(ResumeData(), facts, TODAY, date(2026, 9, 30))

    paths = {w.path.rsplit("/", 1)[-1]: w.value for w in plan.writes}
    assert "position" not in paths
    assert paths["occupation"]["name"] == "생산직"
    assert any("짧아요" in a for a in plan.asks)


def test_none_answers_are_saved_so_the_question_does_not_repeat() -> None:
    facts = ResumeFacts(careers=[CareerFact(position="없음")], no_certifications=True)
    data = ResumeData(careers=[Career(item_id="c1")])
    plan = plan_writes(data, facts, TODAY, date(2026, 9, 30))

    by_path = {w.path: w for w in plan.writes}
    assert by_path["/careers/c1/position"].value == "없음"
    assert by_path["/certifications_status"].status == "not_applicable"
