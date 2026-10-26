import json

import pytest

from app.agent.nodes.respond import FALLBACK_REPLY, parse_output
from app.core.config import get_settings
from app.services.agent_turn import run_conversation

LEE = {
    "separation_date": "2026-08-31",
    "age_at_separation": 58,
    "has_disability": False,
    "recipient_type": "general",
    "stage": "recognition",
    "eligibility_applied_date": "2026-09-15",
    "completed_rounds": 3,
    "last_recognition_date": "2026-11-24",
    "next_recognition_date": "2026-12-22",
    "demo_today": "2026-12-16",
}
PARK = {**LEE, "age_at_separation": 61, "stage": "job_registration", "completed_rounds": 0}


def _data(activities: list | None = None) -> dict:
    resume = {
        "education": [],
        "competencies": {"careers": [], "certifications": []},
        "job_preferences": {"desired_occupations": [], "desired_regions": []},
    }
    return {"resume": resume, "activities": activities or [], "recognition": {}}


def _reply(**fields) -> str:
    return json.dumps({"reply": "알겠어요.", **fields}, ensure_ascii=False)


def test_activity_from_message_updates_round(fake_llm) -> None:
    earlier = [{"date": "2026-12-08", "kind": "job_search", "route": "work24"}]
    activity = {"date": "2026-12-16", "kind": "job_application", "route": "work24"}
    fake_llm([_reply(activities=[activity], next_action="review_form")])

    result = run_conversation(LEE, _data(earlier), ["방금 고용24로 OO물산에 지원했어요"])

    assert result.next_action == "review_form"
    assert result.data["activities"][-1]["evidence"]["required"] == []
    assert result.data["round"]["counted"] == 2
    assert result.data["derived"]["current_round"] == 4
    # 답 끝에 기록 뒤 건수를 규칙 코드 문장으로 덧붙입니다(코드래빗 지적).
    assert "인정된 활동은 2건" in result.replies[-1]
    assert "채웠어요" in result.replies[-1]


def test_career_without_company_merges_into_latest(fake_llm) -> None:
    fake_llm([
        _reply(careers=[{"company_name": "OO산업"}]),
        _reply(careers=[{"start_date": "2004-03"}]),
    ])  # fmt: skip

    result = run_conversation(PARK, _data(), ["OO산업 다녔어요", "2004년 3월부터요"])

    careers = result.data["resume"]["competencies"]["careers"]
    assert len(careers) == 1
    assert careers[0]["start_date"] == "2004-03"
    assert result.replies == ["알겠어요.", "알겠어요."]


def test_code_date_parsing_turns_words_into_values(
    fake_llm, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATE_PARSING", "code")
    get_settings.cache_clear()
    state = {**PARK, "separation_date": "2026-09-30", "demo_today": "2026-10-12"}
    fake_llm([
        _reply(careers=[{"company_name": "OO산업", "start_date": "작년 3월",
                         "end_date": "올 구월"}]),
        _reply(careers=[{"company_name": None, "start_date": "재작년 겨울"}]),
    ])  # fmt: skip
    try:
        result = run_conversation(state, _data(), ["작년 3월부터 올 구월까지", "재작년 겨울부터"])
    finally:
        get_settings.cache_clear()

    careers = result.data["resume"]["competencies"]["careers"]
    assert len(careers) == 1
    assert (careers[0]["start_date"], careers[0]["end_date"]) == ("2025-03", "2026-09")


def test_model_never_sees_resident_number(fake_llm, monkeypatch: pytest.MonkeyPatch) -> None:
    model = fake_llm([_reply()])
    seen: list[str] = []
    original = type(model)._call

    def spy(self, messages, *args, **kwargs):
        seen.extend(str(m.content) for m in messages)
        return original(self, messages, *args, **kwargs)

    monkeypatch.setattr(type(model), "_call", spy)
    run_conversation(PARK, _data(), ["제 주민번호 650101-1234567이에요"])

    assert seen
    assert not any("1234567" in text for text in seen)


def test_broken_json_falls_back_without_changes() -> None:
    output = parse_output("이건 JSON이 아니에요")

    assert output.reply == FALLBACK_REPLY
    assert output.activities == []


def test_fenced_json_is_read() -> None:
    assert parse_output("```json\n" + _reply() + "\n```").reply == "알겠어요."


def test_repeated_preferences_are_kept_once(fake_llm) -> None:
    """코드래빗 지적: 여러 턴에 같은 학력·희망 직종·지역을 말하면 중복으로 쌓이던 문제."""
    again = _reply(desired_occupations=["경비원"], desired_regions=["서울"])
    fake_llm([again, again])

    result = run_conversation(PARK, _data(), ["경비 일 하고 싶어요", "서울에서 경비요"])

    preferences = result.data["resume"]["job_preferences"]
    assert preferences["desired_occupations"] == [{"name": "경비원"}]
    assert preferences["desired_regions"] == ["서울"]


def test_undated_activity_is_not_recorded_and_date_is_asked(fake_llm) -> None:
    """코드래빗 지적: 날짜를 못 정한 활동은 빠지는데 답이 기록했다고 말할 수 있던 문제."""
    activity = {"date": "다음 주쯤", "kind": "job_application", "route": "work24"}
    fake_llm([_reply(activities=[activity])])

    result = run_conversation(LEE, _data(), ["다음 주쯤 고용24로 지원했어요"])

    assert result.data["activities"] == []
    assert "아직 기록하지 않았어요" in result.replies[-1]
