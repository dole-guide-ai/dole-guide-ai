"""이력서 대화 단계(rules/resume/steps): 순서·문구·버튼 답·제안·미루기. 합성 값만 씁니다."""

import json
import re
from datetime import date
from pathlib import Path

import pytest

from app.rules.resume import (
    ResumeStep,
    derive_resume_values,
    question_text,
    resume_steps,
    section_done,
)
from app.rules.resume.steps import (
    ACCEPT,
    DEFERRED_REVIEW,
    NAME_ONLY_ANSWER,
    NEGOTIABLE_SALARY,
    NOT_IN_LIST,
    OCCUPATION_PICK,
    OCCUPATION_UNMATCHED,
    REGION_PICK,
    SAVE_AFTER_FILL,
    templates,
)
from app.schemas.common import FormField
from app.schemas.forms.resume import ResumeData
from app.services.accounts import seed_resume

PERSONAS = Path(__file__).resolve().parents[2] / "data" / "seeds" / "personas.json"

SEPARATION = date(2026, 9, 30)
TODAY = date(2026, 10, 21)
PRONOUN = re.compile(r"그곳|거기|그분|그것|이것|저것|그때")

# 경력 하나(물류, 월급 280만 원)만 채운 이력서
CAREER = {
    "item_id": "c1",
    "company_name": {"value": "OO물류", "status": "confirmed"},
    "start_date": {"value": "2012-03", "status": "confirmed"},
    "end_date": {"value": "2026-09", "status": "confirmed"},
    "position": {"value": "반장", "status": "confirmed"},
    "occupation": {"value": {"code": None, "name": "물류"}, "status": "confirmed"},
    "monthly_salary": {"value": 2_800_000, "status": "confirmed"},
}


def steps(data: ResumeData, **kw) -> list[ResumeStep]:
    kw.setdefault("asked", {})
    kw.setdefault("skip_confirm", True)
    return resume_steps(data, entry_branch="E7a", separation_date=SEPARATION, **kw)


def by_id(data: ResumeData, step_id: str, **kw) -> ResumeStep:
    return next(s for s in steps(data, **kw) if s.id == step_id)


def values(writes) -> dict:
    return {w.path: w.value for w in writes}


def test_required_steps_come_before_recommended() -> None:
    data = ResumeData.model_validate({"careers": [CAREER | {"main_duties": {}}]})
    order = [s.id for s in steps(data)]
    # 그 전 경력(한 번만 묻는 질문)은 경력 바로 뒤에 묻고, 나머지는 꼭 채울 칸이 끝난 뒤에
    # 하던 일·그 밖의 역량을 묻습니다.
    required = [s.required for s in steps(data) if s.id != "resume.career_more"]
    assert required == sorted(required, reverse=True)
    assert order.index("resume.resume_title") < order.index("resume.career_duties")
    assert order[-1] == "resume.save_ready"


def test_proposals_come_from_the_career() -> None:
    data = ResumeData.model_validate({"careers": [CAREER]})
    job = by_id(data, "resume.wish_job")
    assert job.choices[0] == ACCEPT
    # 제안을 받으면 그 이름으로 고용24 직종 후보를 고를 차례가 됩니다.
    assert values(job.answer_writes(ACCEPT)) == {
        "/job_preferences/desired_occupations/o1/occupation": {
            "code": None,
            "name": "물류",
            "status": "needs_confirmation",
            "said": "물류",
        }
    }
    assert question_text(job) == "물류 일을 이어서 하고 싶으세요?"
    wage = by_id(data, "resume.wish_wage")
    assert question_text(wage) == "예전처럼 월 280만 원으로 적을까요?"
    assert values(wage.answer_writes("면접 후 결정할게요")) == {
        "/job_preferences/desired_salary": NEGOTIABLE_SALARY
    }
    title = by_id(data, "resume.resume_title")
    assert values(title.answer_writes(ACCEPT)) == {"/resume_title": "물류 경력 이력서"}


def test_button_answers_write_schema_choices() -> None:
    data = ResumeData.model_validate(
        {
            "careers": [CAREER | {"position": {}}],
            "job_preferences": {
                "desired_occupations": [
                    {"item_id": "o1", "occupation": {"value": {"code": None, "name": "경비"}}}
                ]
            },
        }
    )
    assert values(by_id(data, "resume.career_position").answer_writes("없었어요")) == {
        "/careers/c1/position": "없음"
    }
    assert values(by_id(data, "resume.wish_experience").answer_writes("아니요")) == {
        "/job_preferences/desired_occupations/o1/experience_type": "신입"
    }
    employment = by_id(data, "resume.wish_employment")
    assert values(employment.answer_writes("상관없어요")) == {
        "/job_preferences/employment_contract_type": "관계없음"
    }
    # 병역은 부정을 다시 묻지 않고 해당 여부를 바로 묻습니다. "해당 없어요"면 바로 저장합니다.
    military = by_id(data, "resume.wish_military")
    assert military.choices == ("아니요, 해당 없어요", "네, 해당돼요")
    assert values(military.answer_writes("아니요, 해당 없어요")) == {
        "/job_preferences/military_alternative": "해당 없음"
    }
    # 버튼에 없는 말은 모델이 처리합니다.
    assert employment.answer_writes("정규직이요") is None


def test_deferred_steps_are_skipped_then_reviewed_once() -> None:
    data = ResumeData.model_validate({"careers": [CAREER]})
    first = steps(data)[0]
    assert first.id == "resume.career_more"
    every_required = frozenset(s.key for s in steps(data) if s.required)
    left = steps(data, deferred=every_required | {"resume.career_more"})
    # 꼭 채울 칸을 모두 미뤘으면 미룬 칸 확인을 먼저 묻고, 한 번 답하면 다시 묻지 않습니다.
    assert left[0].id == DEFERRED_REVIEW
    assert left[0].vars == {"count": len(every_required)}
    again = steps(data, deferred=every_required | {"resume.career_more", DEFERRED_REVIEW})
    assert all(not s.required for s in again)
    # 미룬 칸이 남은 채 끝까지 오면 "다 채웠어요" 대신 채운 뒤 저장하라고 안내합니다.
    assert again[-1].id == SAVE_AFTER_FILL
    assert again[-1].vars == {"count": len(every_required)}


def test_previous_company_is_a_chat_only_question() -> None:
    data = ResumeData.model_validate({"careers": [CAREER]})
    panel = resume_steps(data, entry_branch="E7a", separation_date=SEPARATION)
    assert "resume.career_more" not in [s.id for s in panel]
    asked = resume_steps(
        data, entry_branch="E7a", separation_date=SEPARATION, asked={"resume.career_more": 1}
    )
    assert "resume.career_more" not in [s.id for s in asked]


def test_education_year_is_asked_apart_from_school_name() -> None:
    data = ResumeData.model_validate(
        {
            "education": [
                {
                    "item_id": "e1",
                    "education_level": {"value": "고등학교", "status": "confirmed"},
                    "graduation_status": {"value": "졸업", "status": "confirmed"},
                }
            ]
        }
    )
    school = by_id(data, "resume.education_school")
    assert school.key == "resume.education_school:e1"
    assert school.paths == ("/education/e1/school_name",)
    # 연도는 따로 묻고, 모르면 버튼으로 미룹니다.
    period = by_id(data, "resume.education_period")
    assert period.paths == ("/education/e1/start_date", "/education/e1/end_date")
    assert period.choices == ("기억이 안 나요",)
    assert question_text(period).startswith("고등학교 입학 연도와 졸업 연도를")


def test_school_level_is_spoken_plainly() -> None:
    data = ResumeData.model_validate(
        {
            "education": [
                {
                    "item_id": "e1",
                    "education_level": {"value": "대학교(4년제)", "status": "confirmed"},
                }
            ]
        }
    )
    assert question_text(by_id(data, "resume.education_school")).startswith("대학교 이름이 뭐예요?")


def test_a_step_asked_twice_is_held_whoever_asked() -> None:
    """같은 칸을 두 번 물었으면 미룬 칸으로 보고 다음 칸으로 갑니다(퇴사 확인 되풀이 문제)."""
    data = ResumeData.model_validate(
        {"careers": [CAREER | {"end_date": {"value": "2025-04", "status": "extracted"}}]}
    )
    first = steps(data)[0]
    assert first.key == "resume.career_end_check:c1"
    # 퇴사 확인은 한 번만 묻습니다.
    assert "resume.career_end_check:c1" not in [s.key for s in steps(data, asked={first.key: 1})]
    regions = {"resume.wish_region": 2, "resume.career_more": 1}
    assert "resume.wish_region" not in [s.id for s in steps(data, asked=regions)]


# ── 문구 ────────────────────────────────────────────────


def test_fills_company_name() -> None:
    step = ResumeStep("resume.career_duties", {"company": "한빛물류"})
    assert question_text(step).startswith("한빛물류에서는 주로 어떤 일을 하셨어요?")


@pytest.mark.parametrize("step_id", sorted(templates()["questions"]))
def test_no_pronoun_even_when_vars_are_missing(step_id: str) -> None:
    for vars_ in ({}, {"company": None, "year": None, "level": None, "occupation": None}):
        text = question_text(ResumeStep(step_id, vars_))
        assert text and "{" not in text and not PRONOUN.search(text), text


def test_unnamed_and_fallback_wording() -> None:
    assert question_text(ResumeStep("resume.career_period")).startswith("최근에 다니신 회사에는")
    # 회사 이름이 없으면 변수 없는 문구(unnamed)를 씁니다.
    end_check = ResumeStep("resume.career_end_check", {"year": 2026, "month": 9})
    assert question_text(end_check).startswith("실업급여 기준 이직일보다 전에")
    named = ResumeStep("resume.career_end_check", {"company": "OO물류", "year": 2026, "month": 9})
    assert question_text(named).startswith("실업급여 기준 이직일은 2026년 9월인데, OO물류")
    # 말한 표현(quote)이 없는 확인은 패널을 보라고 안내합니다.
    assert "확인 필요" in (question_text(ResumeStep("resume.value_confirm")) or "")


def test_value_written_from_speech_is_confirmed_in_chat() -> None:
    """ "2022년"을 2022년 3월로 바꿔 적었으면 대화가 확인을 묻고, "네, 맞아요"면 확정합니다."""
    data = ResumeData.model_validate({"careers": [CAREER]})
    data.careers[0].start_date = FormField(
        value="2012-03",
        status="extracted",
        source="user_answer",
        transformed=True,
        evidence={"kind": "utterance", "quote": "2012년"},
    )
    first = steps(data)[0]
    assert first.id == "resume.value_confirm"
    assert question_text(first).startswith('"2012년"라고 하신 것을 2012년 3월로 적었어요.')
    (write,) = first.answer_writes("네, 맞아요") or ()
    assert (write.path, write.value) == ("/careers/c1/start_date", "2012-03")
    assert write.status == "confirmed"


def test_plan_view_gives_the_model_paths_choices_and_proposal() -> None:
    from app.agent.nodes.resume import step_view

    data = ResumeData.model_validate({"careers": [CAREER]})
    view = step_view(by_id(data, "resume.wish_employment"))
    assert view["allowed"] == {
        "/job_preferences/employment_contract_type": [
            "기간의 정함이 없는 근로계약",
            "기간의 정함이 있는 근로계약",
            "관계없음",
        ]
    }
    job = step_view(by_id(data, "resume.wish_job"))
    assert job["proposal"]["/job_preferences/desired_occupations/o1/occupation"]["name"] == "물류"
    assert job["reason"] == "OO물류에서 물류 일을 하셨어요"


def test_college_button_leads_to_a_code_step_with_enum_buttons() -> None:
    """ "대학교 졸업"은 저장할 값이 없어 종류를 묻는 단계로 이어지고, 버튼은 스키마 enum입니다."""
    from app.rules.resume.steps import FOLLOW_UPS

    follow = FOLLOW_UPS[("resume.education_level", "대학교 졸업")]
    step = steps(ResumeData(), follow=follow)[0]
    assert step.id == "resume.education_kind"
    assert step.choices == ("대학교(2/3년제)", "대학교(4년제)")
    assert values(step.answer_writes("대학교(4년제)")) == {
        "/education/e1/education_level": "대학교(4년제)",
        "/education/e1/graduation_status": "졸업",
    }


def test_education_without_level_asks_the_kind_not_the_first_question() -> None:
    """말로 "대학교 졸업했어요"만 하면 졸업만 저장되는데, 그때 처음 질문을 되풀이하지 않습니다."""
    data = ResumeData.model_validate(
        {
            "careers": [CAREER],
            "education": [
                {"item_id": "e1", "graduation_status": {"value": "졸업", "status": "extracted"}}
            ],
        }
    )
    first = by_id(data, "resume.education_kind")
    assert first.key == "resume.education_kind:e1"
    assert "resume.education_level" not in [s.id for s in steps(data)]
    assert values(first.answer_writes("대학교(2/3년제)")) == {
        "/education/e1/education_level": "대학교(2/3년제)"
    }


def test_college_asks_major_then_gpa_but_high_school_does_not() -> None:
    def edu(level: str) -> ResumeData:
        return ResumeData.model_validate(
            {
                "careers": [CAREER],
                "education": [
                    {
                        "item_id": "e1",
                        "education_level": {"value": level, "status": "confirmed"},
                        "graduation_status": {"value": "졸업", "status": "confirmed"},
                        "school_name": {"value": "OO대학교", "status": "confirmed"},
                        "start_date": {"value": "2000-03", "status": "confirmed"},
                        "end_date": {"value": "2004-02", "status": "confirmed"},
                    }
                ],
            }
        )

    ids = [s.id for s in steps(edu("대학교(4년제)"))]
    assert ids.index("resume.education_major") < ids.index("resume.wish_job")
    # "몇 점 만점에 몇 점"으로 한 번에 묻고, 값 확인(만점 목록·0~만점 범위)은 저장 규칙이 합니다.
    gpa = by_id(edu("대학교(4년제)"), "resume.education_gpa")
    assert gpa.choices == ("기억이 안 나요",) and not gpa.required
    assert gpa.paths == ("/education/e1/gpa_scale", "/education/e1/gpa")
    assert "resume.education_major" not in [s.id for s in steps(edu("고등학교"))]


def test_military_yes_asks_which_kind_next() -> None:
    data = ResumeData.model_validate({"careers": [CAREER]})
    kind = steps(data, follow="resume.wish_military_kind")[0]
    assert kind.id == "resume.wish_military_kind"
    assert "해당 없음" not in kind.choices and "산업기능요원" in kind.choices
    assert values(kind.answer_writes("산업기능요원")) == {
        "/job_preferences/military_alternative": "산업기능요원"
    }
    assert question_text(kind) == "어떤 병역대체 근무에 해당하세요?"


# ── 고용24 공통코드 고르기 (2-1.4) ──

OCC = "/job_preferences/desired_occupations/o1/occupation"
REGIONS = "/job_preferences/desired_regions"


def _unpicked(said: str) -> dict:
    return {"code": None, "name": said, "status": "needs_confirmation", "said": said}


def _with_wish(occupation: dict, regions: list[dict] | None = None) -> ResumeData:
    prefs: dict = {
        "desired_occupations": [
            {"item_id": "o1", "occupation": {"value": occupation, "status": "extracted"}}
        ]
    }
    if regions is not None:
        prefs["desired_regions"] = {"value": regions, "status": "extracted"}
    return ResumeData.model_validate({"careers": [CAREER], "job_preferences": prefs})


def test_unpicked_occupation_offers_code_candidates() -> None:
    pick = by_id(_with_wish(_unpicked("전기관리")), OCCUPATION_PICK)

    assert pick.choices == ("빌딩 전기관리원", "공장 전기관리원", "아파트 전기관리원", NOT_IN_LIST)
    assert values(pick.answer_writes("아파트 전기관리원")) == {
        OCC: {
            "code": "834001",
            "name": "아파트 전기관리원",
            "status": "confirmed",
            "said": "전기관리",
        }
    }
    assert values(pick.answer_writes(NOT_IN_LIST))[OCC]["status"] == "name_only"
    assert question_text(pick) == (
        "'전기관리' 일과 가장 가까운 고용24 직종을 골라 주세요. "
        "맞는 게 없으면 다른 말로 말씀해 주셔도 돼요."
    )


def test_no_candidate_asks_other_words_or_name_only() -> None:
    step = by_id(_with_wish(_unpicked("우주비행사")), OCCUPATION_UNMATCHED)

    assert step.choices == (NAME_ONLY_ANSWER,)
    assert values(step.answer_writes(NAME_ONLY_ANSWER))[OCC]["status"] == "name_only"


def test_unpicked_region_replaces_only_that_region() -> None:
    picked = {"code": "11350", "name": "서울 노원구", "status": "confirmed", "said": "노원구"}
    data = _with_wish(
        _unpicked("택배원") | {"code": "624100", "status": "confirmed"},
        [
            picked,
            _unpicked("중구"),
        ],
    )
    pick = by_id(data, REGION_PICK)

    assert pick.item == "중구" and NOT_IN_LIST in pick.choices
    written = values(pick.answer_writes("부산 중구"))[REGIONS]
    assert written[0] == picked
    assert (written[1]["code"], written[1]["status"]) == ("26110", "confirmed")


def test_suggested_experience_is_one_proposal_question() -> None:
    # 같은 직종 경력 합계를 코드가 제안하면(확인 필요) 세 칸을 따로 묻지 않고 한 번에 확인받습니다.
    occ = _unpicked("물류") | {"code": "028408", "status": "confirmed"}
    data = _with_wish(occ)
    d = data.job_preferences.desired_occupations[0]
    note = {"kind": "computed", "note": "같은 직종 경력 합계 14년 7개월"}
    for name, value in (
        ("experience_type", "경력"),
        ("experience_years", 14),
        ("experience_months", 7),
    ):
        setattr(
            d, name, FormField(value=value, status="extracted", transformed=True, evidence=note)
        )

    ids = [s.id for s in steps(data, skip_confirm=False)]
    step = by_id(data, "resume.wish_experience")

    assert "resume.value_confirm" not in ids
    assert step.choices[0] == ACCEPT
    assert len(step.answer_writes(ACCEPT)) == 3
    assert question_text(step).startswith("물류 경력을 14년 7개월로 적을까요?")


# ── 판정과 질문이 어긋나지 않음 ──
# 꼭 채울 항목이 덜 찼는데 질문 목록에 그 항목을 묻는 필수 질문이 없으면, 화면은 4/5인데 AI는
# "다 채웠어요"라고 하게 됩니다(박진수 확인 값, 최영수 직종 확인 필요가 이 모양이었음).

SECTION_OF_HEAD = {"careers_status": "careers", "certifications_status": "certifications"}


def _section(path: str) -> str:
    head = path.strip("/").split("/")[0]
    return SECTION_OF_HEAD.get(head, head)


def _seed_resumes() -> dict[str, ResumeData]:
    raw = json.loads(PERSONAS.read_text(encoding="utf-8"))
    out = {}
    for persona in raw if isinstance(raw, list) else raw["personas"]:
        if resume := persona.get("resume"):
            data = seed_resume(resume["data"], resume["field_status"])
            out[persona["persona_id"]] = derive_resume_values(data, SEPARATION)
    return out


def _mutations() -> dict[str, tuple[ResumeData, str]]:
    """이정호 이력서에서 칸 하나를 비우거나 고르기 전으로 바꾼 상태와, 그 칸을 묻는 질문의 경로."""
    base = _seed_resumes()["lee"]
    cases = {}

    def case(name: str, path: str, change) -> None:
        data = base.model_copy(deep=True)
        change(data)
        cases[name] = (data, path)

    occ = "/job_preferences/desired_occupations/occ_001/occupation"
    case("제목 없음", "/resume_title", lambda d: setattr(d, "resume_title", FormField()))
    case("학력 없음", "/education", lambda d: setattr(d, "education", []))
    case(
        "직종 고르기 전",
        occ,
        lambda d: setattr(
            d.job_preferences.desired_occupations[0],
            "occupation",
            FormField(value=_unpicked("물류"), status="extracted"),
        ),
    )
    case(
        "직종 후보 없음",
        occ,
        lambda d: setattr(
            d.job_preferences.desired_occupations[0],
            "occupation",
            FormField(value=_unpicked("우주비행사"), status="extracted"),
        ),
    )
    case(
        "지역 고르기 전",
        REGIONS,
        lambda d: setattr(
            d.job_preferences,
            "desired_regions",
            FormField(value=[_unpicked("중구")], status="extracted"),
        ),
    )
    case(
        "경력 합계 확인 전",
        "/job_preferences/desired_occupations/occ_001/experience",
        _suggest_experience,
    )
    case(
        "월급 없음",
        "/job_preferences/desired_salary",
        lambda d: setattr(d.job_preferences, "desired_salary", FormField()),
    )
    case(
        "직급 없음",
        "/careers/career_001/position",
        lambda d: setattr(d.careers[0], "position", FormField()),
    )
    case(
        "자격 답 없음",
        "/certifications",
        _no_certifications,
    )
    return cases


def _no_certifications(data: ResumeData) -> None:
    data.certifications = []
    data.certifications_status = FormField()


def _suggest_experience(data: ResumeData) -> None:
    d = data.job_preferences.desired_occupations[0]
    note = {"kind": "computed", "note": "같은 직종 경력 합계 25년 5개월"}
    for name, value in (
        ("experience_type", "경력"),
        ("experience_years", 25),
        ("experience_months", 5),
    ):
        setattr(
            d, name, FormField(value=value, status="extracted", transformed=True, evidence=note)
        )


def _asks(asked: list[ResumeStep], path: str) -> bool:
    return any(s.required and any(p.startswith(path) for p in s.paths) for s in asked)


@pytest.mark.parametrize("skip_confirm", [False, True], ids=["패널", "대화"])
@pytest.mark.parametrize("name", list(_seed_resumes()))
def test_every_unfinished_seed_section_has_a_required_question(
    name: str, skip_confirm: bool
) -> None:
    data = _seed_resumes()[name]
    asked = steps(data, skip_confirm=skip_confirm)

    for section, done in section_done(data).items():
        assert done or any(
            s.required and any(_section(p) == section for p in s.paths) for s in asked
        ), f"{name}: {section}이(가) 덜 찼는데 묻는 질문이 없음 {[s.id for s in asked]}"


@pytest.mark.parametrize("skip_confirm", [False, True], ids=["패널", "대화"])
@pytest.mark.parametrize("name", list(_mutations()))
def test_unfinished_field_is_asked(name: str, skip_confirm: bool) -> None:
    data, path = _mutations()[name]

    assert not all(section_done(data).values())
    assert _asks(steps(data, skip_confirm=skip_confirm), path), name


def test_retry_card_puts_the_reason_before_the_same_question() -> None:
    from app.rules.resume import retry_text

    data = ResumeData.model_validate({"careers": [CAREER | {"start_date": {}, "end_date": {}}]})
    period = by_id(data, "resume.career_period")
    reason = "'봄쯤'은(는) 몇 년 몇 월인지 알 수 없어서 적지 못했어요."

    assert retry_text(period, [reason]) == f"{reason} {question_text(period)}"
    # 이유를 모를 때(모델이 값을 못 옮김)도 같은 문구를 그대로 되풀이하지 않습니다.
    assert retry_text(period, []).startswith("말씀하신 내용으로는 이 칸을 적지 못했어요.")
