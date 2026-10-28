"""이력서 사실 → 칸 쓰기 (rules/resume/facts.py). 기준일 2026-10-12, 퇴사일 2026-09-30."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.rules.resume import normalize_date
from app.rules.resume.facts import (
    ASK_DUTIES,
    ASK_WHICH_CAREER,
    ASK_WHICH_SCHOOL,
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
    fact = CareerFact(company_name="OO산업", start="작년 삼월", end="올 구월")
    plan = _plan(ResumeFacts(careers=[fact]))

    values = _values(plan)
    assert (values["/careers/c1/start_date"], values["/careers/c1/end_date"]) == (
        "2025-03",
        "2026-09",
    )
    assert all(
        w.transformed for w in plan.writes if w.path.endswith("_date")
    )  # 바꾼 값은 확인 필요


def test_vague_start_asks_and_creates_no_empty_career() -> None:
    plan = _plan(ResumeFacts(careers=[CareerFact(start="재작년 겨울")]))

    assert plan.writes == []
    assert plan.asks


def test_item_id_targets_the_existing_career_and_is_required_without_company() -> None:
    data = ResumeData(careers=[Career(item_id="c7")])

    plan = _plan(ResumeFacts(careers=[CareerFact(item_id="c7", position="반장")]), data)
    assert _values(plan) == {"/careers/c7/position": "반장"}

    # 회사 이름도 item_id도 없고 지금 묻는 경력도 없으면 추측하지 않고 회사 이름을 묻습니다.
    # 사용자에게 보이는 질문에 item_id 같은 코드 말은 넣지 않습니다(골든셋 F-001 답에 노출됨).
    vague = _plan(ResumeFacts(careers=[CareerFact(position="반장")]), data)
    assert vague.writes == [] and vague.asks == [ASK_WHICH_CAREER]
    assert "item_id" not in " ".join(vague.asks) and vague.diagnostics
    wrong = _plan(ResumeFacts(careers=[CareerFact(item_id="c9", position="반장")]), data)
    assert wrong.writes == [] and wrong.asks == [] and wrong.diagnostics


def test_period_without_company_goes_to_the_career_being_asked() -> None:
    # "언제부터 다니셨어요?"(c1 기간 질문)에 "작년 3월부터 올해 9월까지요"(골든셋 F-001·F-010)
    data = ResumeData(careers=[Career(item_id="c1")])
    facts = ResumeFacts(careers=[CareerFact(start="작년 3월", end="올해 9월")])

    plan = plan_writes(
        data, facts, TODAY, SEPARATION, asking=("/careers/c1/start_date", "/careers/c1/end_date")
    )

    assert _values(plan) == {"/careers/c1/start_date": "2025-03", "/careers/c1/end_date": "2026-09"}


def test_spoken_acquired_date_is_calculated_like_other_dates() -> None:
    # 골든셋 F-031: "작년 12월에 딴 지게차" → 취득일이 비던 문제. 바꾼 표시와 원래 표현을 남깁니다.
    def acquired(expr: str):
        cert = CertificationFact(certificate_name="지게차", acquired=expr)
        plan = _plan(ResumeFacts(certifications=[cert]))
        return next(w for w in plan.writes if w.path.endswith("/acquired_date"))

    spoken = acquired("작년 12월")
    assert (spoken.value, spoken.transformed) == ("2025-12", True)
    # 서류에 적힌 날짜는 말한 만큼 그대로 씁니다.
    assert (acquired("2011.05.20").value, acquired("2011.05.20").transformed) == (
        "2011-05-20",
        False,
    )


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
    # 직종·지역은 고용24 공통코드 후보를 고를 차례로 둡니다(모델이 코드를 고르지 않음).
    assert values["/job_preferences/desired_occupations/o1/occupation"] == {
        "code": None,
        "name": "생산직",
        "status": "needs_confirmation",
        "said": "생산직",
    }
    assert values["/job_preferences/desired_regions"] == [
        {"code": None, "name": "경기 화성", "status": "needs_confirmation", "said": "경기 화성"}
    ]


def test_exact_code_name_is_confirmed_right_away() -> None:
    values = _values(_plan(ResumeFacts(desired_occupations=["택배원"], desired_regions=["노원구"])))

    assert values["/job_preferences/desired_occupations/o1/occupation"]["code"] == "624100"
    assert values["/job_preferences/desired_regions"][0]["code"] == "11350"


def test_new_word_replaces_the_occupation_not_picked_yet() -> None:
    # 아직 고르지 않은 직종("시설관리")을 "전기관리"로 다시 말하면 항목을 늘리지 않고 바꿉니다.
    first = _saved(ResumeData(), _plan(ResumeFacts(desired_occupations=["시설관리"])))
    again = _saved(first, _plan(ResumeFacts(desired_occupations=["전기관리"]), first))

    occupations = again.job_preferences.desired_occupations
    assert [d.item_id for d in occupations] == ["o1"]
    assert occupations[0].occupation.value["said"] == "전기관리"


def test_saying_a_picked_occupation_or_region_again_keeps_the_pick() -> None:
    picked = {
        "code": "834001",
        "name": "아파트 전기관리원",
        "status": "confirmed",
        "said": "시설관리",
    }
    region = {"code": "41190", "name": "경기 부천시", "status": "confirmed", "said": "부천"}
    data = ResumeData.model_validate(
        {
            "job_preferences": {
                "desired_occupations": [{"item_id": "o1", "occupation": {"value": picked}}],
                "desired_regions": {"value": [region]},
            }
        }
    )

    values = _values(
        _plan(ResumeFacts(desired_occupations=["시설관리"], desired_regions=["부천"]), data)
    )

    assert not any(p.endswith("/occupation") for p in values)
    assert values["/job_preferences/desired_regions"] == [region]


def test_spoken_month_and_short_year_word() -> None:
    assert normalize_date("올 구월", TODAY, SEPARATION).value == "2026-09"
    assert normalize_date("올렸어요", TODAY, SEPARATION).value is None


def test_occupation_and_position_go_to_separate_fields() -> None:
    fact = CareerFact(company_name="대성기계", occupation="생산직", position="반장")

    values = _values(_plan(ResumeFacts(careers=[fact])))

    assert values["/careers/c1/position"] == "반장"
    assert values["/careers/c1/occupation"]["name"] == "생산직"


def test_short_duties_ask_for_more() -> None:
    facts = ResumeFacts(careers=[CareerFact(company_name="한빛물류", main_duties="포장")])
    plan = plan_writes(ResumeData(), facts, TODAY, date(2026, 9, 30))

    assert plan.asks == [ASK_DUTIES.format(company="한빛물류")]


def test_education_values_are_schema_choices_and_details_join_the_existing_item() -> None:
    data = ResumeData.model_validate(
        {"education": [{"item_id": "e1", "education_level": {"value": "고등학교"}}]}
    )
    # 학교 이름만 오면 어느 학력인지 묻습니다(e2로 새로 생기던 문제).
    vague = _plan(ResumeFacts(education=[EducationFact(school_name="OO고등학교")]), data)
    assert vague.writes == [] and vague.asks == [ASK_WHICH_SCHOOL]
    plan = _plan(
        ResumeFacts(education=[EducationFact(item_id="e1", school_name="OO고등학교")]), data
    )
    assert _values(plan) == {"/education/e1/school_name": "OO고등학교"}
    # 선택지 밖의 값은 도구 입력에서 거절됩니다(모델이 스키마 값으로 옮김).
    with pytest.raises(ValidationError):
        EducationFact(education_level="고졸")


def test_none_answers_are_saved_so_the_question_does_not_repeat() -> None:
    facts = ResumeFacts(careers=[CareerFact(item_id="c1", position="없음")], no_certifications=True)
    data = ResumeData(careers=[Career(item_id="c1")])
    plan = plan_writes(data, facts, TODAY, date(2026, 9, 30))

    by_path = {w.path: w for w in plan.writes}
    assert by_path["/careers/c1/position"].value == "없음"
    assert by_path["/certifications_status"].status == "not_applicable"


def test_certification_date_is_kept_to_the_month() -> None:
    """ "2025년 9월"은 2025-09로 두고, 말하지 않은 "1일"을 붙이지 않습니다."""
    for said, expected in (("2025년 9월", "2025-09"), ("2011년", "2011")):
        fact = CertificationFact(certificate_name="기사", acquired=said)
        assert (
            _values(_plan(ResumeFacts(certifications=[fact])))["/certifications/q1/acquired_date"]
            == expected
        )


def test_certification_issuer_and_full_date_from_document() -> None:
    # 골든셋 F-020: 자격증 사진의 발급 기관과 취득일(일까지)
    fact = CertificationFact(
        certificate_name="지게차운전기능사",
        acquired="2011. 05. 20.",
        issuing_organization="한국산업인력공단",
    )

    values = _values(_plan(ResumeFacts(certifications=[fact])))

    assert values["/certifications/q1/issuing_organization"] == "한국산업인력공단"
    assert values["/certifications/q1/acquired_date"] == "2011-05-20"


@pytest.mark.parametrize("acquired", ["2011. 02. 30.", "2011.13", "2011.05.201"])
def test_impossible_acquired_date_is_asked_again(acquired: str) -> None:
    fact = CertificationFact(certificate_name="지게차운전기능사", acquired=acquired)

    plan = _plan(ResumeFacts(certifications=[fact]))

    assert "/certifications/q1/acquired_date" not in _values(plan)
    assert any(acquired in ask for ask in plan.asks)


# ── 같은 말을 다시 해도 같은 항목(멱등) ─────────────────────


def _saved(data: ResumeData, plan) -> ResumeData:
    """계획한 쓰기를 이력서 데이터에 적용한 결과(다음 턴의 이력서)."""
    raw = data.model_dump(mode="json")
    for w in plan.writes:
        section, item_id, name = w.path.strip("/").rsplit("/", 2)[-3:]
        target = raw
        for part in section.split("/"):
            target = target[part]
        item = next((i for i in target if i["item_id"] == item_id), None)
        if item is None:
            item = {"item_id": item_id}
            target.append(item)
        item[name] = {"value": w.value, "status": w.status, "source": w.source}
    return ResumeData.model_validate(raw)


def test_saying_the_same_items_again_updates_them_instead_of_adding() -> None:
    facts = ResumeFacts(
        careers=[CareerFact(company_name="(주)OO산업")],
        education=[EducationFact(education_level="고등학교", school_name="OO고")],
        certifications=[CertificationFact(certificate_name="지게차운전기능사")],
        desired_occupations=["물류 관리"],
    )
    once = _saved(ResumeData(), _plan(facts))
    again = _plan(
        ResumeFacts(
            careers=[CareerFact(company_name="OO산업 주식회사")],
            education=[EducationFact(education_level="고등학교", end="1990년")],
            certifications=[CertificationFact(certificate_name="지게차운전기능사 ")],
            desired_occupations=["물류관리"],
        ),
        once,
    )
    twice = _saved(once, again)

    assert [c.item_id for c in twice.careers] == ["c1"]
    assert [e.item_id for e in twice.education] == ["e1"]
    assert twice.education[0].end_date.value == "1990-02"
    assert [q.item_id for q in twice.certifications] == ["q1"]
    assert len(twice.job_preferences.desired_occupations) == 1


def test_two_new_items_in_one_turn_get_their_own_ids() -> None:
    # 예전에는 둘 다 len+1(c1)이라 한 항목으로 합쳐졌습니다.
    plan = _plan(
        ResumeFacts(
            careers=[CareerFact(company_name="OO물류"), CareerFact(company_name="OO기계")],
            certifications=[
                CertificationFact(certificate_name="지게차운전기능사"),
                CertificationFact(certificate_name="정보처리기사"),
            ],
        )
    )
    values = _values(plan)
    assert values["/careers/c1/company_name"] == "OO물류"
    assert values["/careers/c2/company_name"] == "OO기계"
    assert values["/certifications/q2/certificate_name"] == "정보처리기사"


def test_new_item_does_not_take_an_id_left_by_a_removed_one() -> None:
    # q1을 지워 q2만 남았을 때 새 자격증이 len+1(q2)로 기존 항목을 덮어쓰던 문제
    data = ResumeData.model_validate(
        {"certifications": [{"item_id": "q2", "certificate_name": {"value": "정보처리기사"}}]}
    )
    cook = CertificationFact(certificate_name="조리기능사")
    plan = _plan(ResumeFacts(certifications=[cook]), data)

    assert "/certifications/q2/certificate_name" not in _values(plan)
    assert _values(plan)["/certifications/q3/certificate_name"] == "조리기능사"


def test_fourth_desired_occupation_is_rejected_not_failing_the_turn() -> None:
    names = ["물류", "경비", "조리", "청소"]
    plan = _plan(ResumeFacts(desired_occupations=names))

    assert sum(p.endswith("/occupation") for p in _values(plan)) == 3
    assert any("청소" in r for r in plan.rejected)


def _college(scale: str | None) -> ResumeData:
    return ResumeData.model_validate(
        {
            "education": [
                {
                    "item_id": "e1",
                    "education_level": {"value": "대학교(4년제)", "status": "confirmed"},
                    "gpa_scale": {"value": scale, "status": "confirmed" if scale else "missing"},
                }
            ]
        }
    )


@pytest.mark.parametrize(
    ("scale", "gpa", "saved"),
    [
        ("4.5", "3.8", "3.8"),
        ("4.5", "3.8점", "3.8"),
        ("4.5", "4.7", None),  # 만점보다 큼
        ("100", 88, "88"),
        (None, "삼점팔", None),  # 숫자가 아님
    ],
)
def test_gpa_is_a_number_from_zero_to_the_scale(scale, gpa, saved) -> None:
    from app.rules.resume.facts import answer_writes

    plan = answer_writes(_college(scale), ("/education/e1/gpa",), gpa, TODAY, SEPARATION)

    assert _values(plan).get("/education/e1/gpa") == saved
    assert bool(plan.asks) is (saved is None)


def test_scale_and_gpa_said_together_are_normalized() -> None:
    from app.rules.resume.facts import answer_writes

    paths = ("/education/e1/gpa_scale", "/education/e1/gpa")
    together = answer_writes(
        _college(None), paths, {"gpa_scale": "4.5점", "gpa": 3.8}, TODAY, SEPARATION
    )
    assert _values(together) == {"/education/e1/gpa_scale": "4.5", "/education/e1/gpa": "3.8"}

    # 목록에 없는 만점은 사람 말로 이유를 돌려줍니다(선택지 목록을 그대로 내밀지 않음).
    odd = answer_writes(_college(None), paths, {"gpa_scale": 4.8, "gpa": 3.8}, TODAY, SEPARATION)
    assert "/education/e1/gpa_scale" not in _values(odd)
    assert odd.asks == ["학점 만점은 4.0·4.3·4.5·5.0·100점 중 하나예요."]


def test_wrong_scale_holds_the_gpa_and_negative_gpa_is_refused() -> None:
    from app.rules.resume.facts import answer_writes

    paths = ("/education/e1/gpa_scale", "/education/e1/gpa")
    # 함께 말한 만점이 틀리면 학점도 두지 않습니다(나중에 만점만 고치면 학점이 만점을 넘을 수 있음).
    odd = answer_writes(_college(None), paths, {"gpa_scale": 4.8, "gpa": 4.7}, TODAY, SEPARATION)
    assert _values(odd) == {}
    negative = answer_writes(_college("4.5"), ("/education/e1/gpa",), "-1", TODAY, SEPARATION)
    assert _values(negative) == {}
    assert negative.asks


def test_same_license_name_again_keeps_the_chosen_code() -> None:
    chosen = {"code": None, "name": "정보처리", "status": "name_only", "said": "정보처리"}
    data = ResumeData.model_validate(
        {
            "certifications": [
                {
                    "item_id": "q1",
                    "certificate_name": {"value": "정보처리", "status": "confirmed"},
                    "certificate_code": {"value": chosen, "status": "confirmed"},
                }
            ]
        }
    )

    values = _values(
        _plan(ResumeFacts(certifications=[CertificationFact(certificate_name="정보처리")]), data)
    )

    assert "/certifications/q1/certificate_code" not in values


def test_other_name_said_for_a_code_field_goes_to_the_name_field() -> None:
    from app.rules.resume.facts import answer_writes

    data = ResumeData.model_validate(
        {
            "certifications": [
                {
                    "item_id": "q1",
                    "certificate_name": {"value": "정보처리", "status": "confirmed"},
                }
            ]
        }
    )
    base = "/certifications/q1"

    values = _values(
        answer_writes(data, (f"{base}/certificate_code",), "정보처리기사", TODAY, SEPARATION)
    )

    # 코드 칸에 글자를 두지 않고, 이름 칸을 고친 뒤 이름으로 코드를 다시 찾습니다.
    assert values[f"{base}/certificate_name"] == "정보처리기사"
    assert values[f"{base}/certificate_code"]["code"] == "5001320"


def test_region_pick_answer_replaces_only_that_region() -> None:
    from app.rules.resume.facts import answer_writes

    picked = {"code": "11350", "name": "서울 노원구", "status": "confirmed", "said": "노원구"}
    open_ = {"code": None, "name": "중구", "status": "needs_confirmation", "said": "중구"}
    data = ResumeData.model_validate(
        {"job_preferences": {"desired_regions": {"value": [picked, open_]}}}
    )
    path = "/job_preferences/desired_regions"

    plan = answer_writes(data, (path,), ["부산 중구"], TODAY, SEPARATION, replacing_region="중구")

    assert [r["name"] for r in _values(plan)[path]] == ["서울 노원구", "부산 중구"]


def test_lowering_only_the_scale_is_refused_when_the_gpa_no_longer_fits() -> None:
    from app.rules.resume.facts import answer_writes

    data = _college("4.5")
    data.education[0].gpa.value = "4.3"

    plan = answer_writes(data, ("/education/e1/gpa_scale",), "4.0", TODAY, SEPARATION)

    assert _values(plan) == {}
    assert plan.asks == ["학점은 0~4.0점 사이로 적어 주세요."]
