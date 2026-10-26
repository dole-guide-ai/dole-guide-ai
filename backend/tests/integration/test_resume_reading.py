"""이력서 읽기 결과(Reading) → 코드 저장(save_answer). 모델 없이 읽은 값으로 검증·저장을 봅니다."""

from collections.abc import Callable
from datetime import datetime, time

import pytest
from sqlalchemy.orm import Session

from app.agent.nodes import resume as node
from app.agent.nodes.resume import Correction, FieldValue, Reading
from app.agent.tools import ToolContext
from app.core.clock import KST
from app.rules.resume.facts import CareerFact, EducationFact, ResumeFacts
from app.services import resume as resume_service
from app.services.accounts import AccountContext
from conftest import TEST_TODAY

pytestmark = pytest.mark.integration
NOW = datetime.combine(TEST_TODAY, time(10, 0), KST)


@pytest.fixture
def park(db_session: Session, entered_account: Callable[[str], AccountContext]) -> ToolContext:
    return ToolContext(db_session, entered_account("park"), TEST_TODAY, NOW)


def memory(pending_key: str | None = None) -> node.ResumeMemory:
    """save_answer는 단계를 직접 받으므로 여기서는 빈 기억만 만듭니다."""
    del pending_key
    return {"asked": {}, "deferred": [], "pending": None, "outcome": {}, "handled": False}


def step_of(ctx: ToolContext, mem: node.ResumeMemory, key: str):
    return next(s for s in node._steps(ctx, mem) if s.key == key)


def data_of(ctx: ToolContext):
    return resume_service.read_resume(ctx.db, ctx.account).data


def with_career(ctx: ToolContext) -> None:
    """첫 경력 질문에 회사 이름만 말한 상태."""
    mem = memory("resume.career_new")
    facts = ResumeFacts(careers=[CareerFact(company_name="OO산업")])
    node.save_answer(
        ctx, mem, step_of(ctx, mem, "resume.career_new"), Reading(kind="value", facts=facts)
    )


def test_facts_from_free_text_are_saved_with_code_decided_paths(park: ToolContext) -> None:
    """첫 경력 질문에 회사·기간을 말하면 facts로 읽혀 코드가 칸·날짜를 정해 저장합니다."""
    mem = memory("resume.career_new")
    facts = ResumeFacts(
        careers=[CareerFact(company_name="OO산업", start="2004년 3월", end="지금까지")]
    )

    out = node.save_answer(
        park, mem, step_of(park, mem, "resume.career_new"), Reading(kind="value", facts=facts)
    )

    saved = out["outcome"]["saved"]
    assert saved["/careers/c1/company_name"] == "OO산업"
    assert saved["/careers/c1/start_date"] == "2004-03"
    assert out["pending"] is None


def test_value_for_a_choice_field_outside_schema_is_rejected(park: ToolContext) -> None:
    with_career(park)
    mem = memory("resume.wish_employment")
    step = step_of(park, mem, "resume.wish_employment")

    out = node.save_answer(park, mem, step, Reading(kind="value", value="정규직"))

    assert "saved" not in out["outcome"]
    assert "/job_preferences/employment_contract_type" in out["outcome"]["rejected"][0]
    ok = node.save_answer(
        park, memory("resume.wish_employment"), step, Reading(kind="value", value="관계없음")
    )
    assert ok["outcome"]["saved"] == {"/job_preferences/employment_contract_type": "관계없음"}


def test_spoken_period_is_turned_into_year_month_or_asked_again(park: ToolContext) -> None:
    with_career(park)
    mem = memory("resume.career_period:c1")
    step = step_of(park, mem, "resume.career_period:c1")

    vague = node.save_answer(
        park,
        memory("resume.career_period:c1"),
        step,
        Reading(kind="value", value={"start": "재작년 겨울", "end": "지금까지"}),
    )
    assert "clarify" in vague["outcome"]
    assert vague["outcome"]["saved"] == {"/careers/c1/end_date": "2026-09"}  # 확실한 쪽만 저장

    clear = node.save_answer(
        park,
        memory("resume.career_period:c1"),
        step,
        Reading(kind="value", value={"start": "2012년 3월"}),
    )
    assert clear["outcome"]["saved"] == {"/careers/c1/start_date": "2012-03"}
    assert data_of(park).careers[0].start_date.value == "2012-03"


def test_not_known_defers_and_off_topic_keeps_the_question(park: ToolContext) -> None:
    with_career(park)
    mem = memory("resume.career_period:c1")
    step = step_of(park, mem, "resume.career_period:c1")

    deferred = node.save_answer(
        park, memory("resume.career_period:c1"), step, Reading(kind="not_known")
    )
    assert deferred["deferred"] == ["resume.career_period:c1"] and deferred["pending"] is None

    # 딴 얘기면 "방금 낸 질문"의 정의(to_pending)가 그대로 남아 다음 턴에 돌아옵니다.
    waiting = memory()
    waiting["pending"] = step.to_pending("언제부터 언제까지 다니셨어요?")
    aside = node.save_answer(park, waiting, step, Reading(kind="off_topic"))
    assert aside["outcome"] == {"off_topic": True}
    assert node.pending_step(aside) is not None
    assert node.pending_step(aside).key == "resume.career_period:c1"


def test_region_list_and_education_choice_and_correction(park: ToolContext) -> None:
    with_career(park)
    region = node.save_answer(
        park,
        memory("resume.wish_region"),
        step_of(park, memory(), "resume.wish_region"),
        Reading(kind="value", value=["인천", "부천", "김포", "서울"]),
    )
    assert [r["name"] for r in region["outcome"]["saved"]["/job_preferences/desired_regions"]] == [
        "인천",
        "부천",
        "김포",
    ]

    # 학력은 모델이 스키마 값으로 넘기고, 선택지 밖("고졸")은 도구 입력에서 거절됩니다.
    edu = ResumeFacts(
        education=[EducationFact(education_level="고등학교", graduation_status="졸업")]
    )
    node.save_answer(park, memory(), None, Reading(kind="value", facts=edu))
    assert data_of(park).education[0].education_level.value == "고등학교"

    fixed = node.save_answer(
        park,
        memory(),
        None,
        Reading(
            kind="correction",
            correction=Correction(path="/careers/c1/company_name", value="OO산업(주)"),
        ),
    )
    assert fixed["outcome"]["saved"] == {"/careers/c1/company_name": "OO산업(주)"}
    bad = node.save_answer(
        park,
        memory(),
        None,
        Reading(
            kind="correction", correction=Correction(path="/careers/c9/company_name", value="x")
        ),
    )
    assert "saved" not in bad["outcome"]


def test_fields_outside_facts_are_saved_by_schema_path(park: ToolContext) -> None:
    """희망 월급·고용형태·병역·운전·차량처럼 facts에 없는 칸은 경로로 받아 검증해 저장합니다."""
    with_career(park)
    salary = {"amount": 3_000_000, "unit": "monthly", "currency": "KRW", "negotiable": False}
    reading = Reading(
        kind="none",
        fields=[
            FieldValue(path="/job_preferences/desired_regions", value=["강원", "서울", "경기"]),
            FieldValue(path="/job_preferences/desired_salary", value=salary),
            FieldValue(path="/job_preferences/employment_contract_type", value="관계없음"),
            FieldValue(path="/job_preferences/military_alternative", value="해당 없음"),
            FieldValue(path="/additional_info/owns_vehicle", value=True),
            FieldValue(path="/additional_info/can_drive", value=True),
            FieldValue(path="/job_preferences/no_such_field", value="x"),  # 없는 경로는 버림
        ],
    )

    out = node.save_answer(park, memory(), None, reading)

    saved = out["outcome"]["saved"]
    assert [r["name"] for r in saved["/job_preferences/desired_regions"]] == [
        "강원",
        "서울",
        "경기",
    ]
    assert saved["/job_preferences/desired_salary"]["amount"] == 3_000_000
    assert saved["/job_preferences/military_alternative"] == "해당 없음"
    assert saved["/additional_info/owns_vehicle"] is True
    assert "/job_preferences/no_such_field" not in saved
    assert data_of(park).job_preferences.employment_contract_type.value == "관계없음"
