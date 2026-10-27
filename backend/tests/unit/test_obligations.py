"""답에 꼭 들어가야 할 사실(rules/obligations)과 기록 전 인정 판정(rules/rounds.admission)."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.nodes import finish as finish_node
from app.rules.obligations import (
    Obligation,
    from_deadline,
    from_mentions,
    from_pii,
    from_round,
    from_scope,
    from_tool_result,
    missing,
    prompt_block,
)
from app.rules.rounds import admission
from app.schemas.messages import DoneEvent, TokenEvent
from app.schemas.rounds import ActivityStatus, LimitsUsed

ROUND = {
    "round": 8,
    "period_start": "2026-11-25",
    "period_end": "2026-12-22",
    "recognition_date": "2026-12-22",
    "d_day": 6,
    "required": 4,
    "counted": 1,
    "remaining": 3,
    "remaining_job_search": 3,
    "required_job_search": 4,
    "job_search_only": True,
    "interval_days": 7,
    "attendance_required": False,
    "not_counted": [{"date": "2026-12-08", "status": "same_day"}],
    "now_time": "10:00",
    "rule_refs": ["ACT-030"],
}


def _keys(obligations: list[Obligation]) -> list[str]:
    return [o.key for o in obligations]


def test_round_panel_gets_shortfall_interval_and_same_day() -> None:
    # 골든셋 P-055(8차 1주 규칙)·P-007(같은 날 2건은 1건, 다른 날에)
    duties = from_round(ROUND, "round")

    assert _keys(duties) == ["round:remaining", "round:interval", "round:same_day:2026-12-08"]
    assert "1주마다 구직활동" in duties[1].text


def test_job_search_shortfall_is_a_duty_when_other_activities_could_fill_count() -> None:
    # 골든셋 P-084: 특강 2건으로 건수는 찼어도 구직활동 1건이 모자람
    round_ = ROUND | {
        "remaining": 0,
        "remaining_job_search": 1,
        "required_job_search": 1,
        "job_search_only": False,
        "interval_days": None,
        "not_counted": [],
    }

    duties = from_round(round_, "round")

    assert _keys(duties) == ["round:job_search"]
    assert duties[0].satisfied_by("구직활동 1건이 더 필요해요")


def test_first_round_is_education_and_some_rounds_take_non_job_search() -> None:
    # 골든셋 P-060: 65세 이상 1차는 교육으로 채움(교육 방식은 유형마다 다름)
    first = ROUND | {"round": 1, "required": 1, "required_job_search": 0, "interval_days": None}
    (education,) = [o for o in from_round(first, "round", "age65_or_disabled")
                    if o.key == "round:first_education"]  # fmt: skip
    assert "온라인" in education.text and education.satisfied_by("교육을 들으면 돼요")
    # 골든셋 P-082: 구직활동을 따로 요구하지 않는 회차는 구직 외 활동으로도 채울 수 있음
    second = first | {"round": 2}
    assert "round:non_job_search_ok" in _keys(from_round(second, "round"))


@pytest.mark.parametrize(
    ("said", "group", "round_no", "used", "key"),
    [
        ("취업특강 들은 것도 넣어 주세요", "repeat", 3, {}, "kind:lecture"),  # P-013
        ("특강은 몇 번까지 돼요?", "general", 2, {"lecture": 1}, "limit:lecture"),  # P-012
        ("훈련 등록만 했는데요", "general", 4, {}, "hours:training"),  # P-102
        ("봉사활동도 쳐 주나요?", "general", None, {}, "kind:volunteer"),  # P-021
        ("영어학원 다니는 것도 돼요?", "general", 2, {}, "kind:private_academy"),  # P-019
    ],
)
def test_mentioned_activity_gets_rule_table_fact(
    said: str, group: str, round_no: int | None, used: dict, key: str
) -> None:
    duties = from_mentions(said, "guide", group=group, round_no=round_no, limits_used=used)

    assert key in _keys(duties)


def test_job_search_mentions_and_resume_panel_get_nothing() -> None:
    assert from_mentions("면접 봤어요", "round", group="general", round_no=4) == []
    assert from_mentions("특강 들었어요", "resume", group="general", round_no=4) == []


def test_round_facts_are_not_duties_outside_round_panels() -> None:
    assert from_round(ROUND, "guide") == []
    assert from_round(None, "round") == []


@pytest.mark.parametrize(
    ("now_time", "said", "ok"),
    [
        # 골든셋 P-017·P-018: 17시 전에는 17시를, 17~18시에는 지났다는 것과 18시를 말해야 함
        ("16:50", "오늘 17:00까지 보내면 돼요", True),
        ("17:20", "지금 보내면 돼요. 17시까지예요", False),
        ("17:20", "17시가 지났어요. 18시까지 고용센터에 가세요", True),
        ("18:30", "마감이 지났어요. 관할 고용센터에 확인하세요", True),
    ],
)
def test_deadline_duty_follows_the_clock(now_time: str, said: str, ok: bool) -> None:
    (duty,) = from_deadline(ROUND | {"d_day": 0, "now_time": now_time})

    assert duty.satisfied_by(said) is ok


def test_no_deadline_duty_before_recognition_day_or_on_attendance_round() -> None:
    assert from_deadline(ROUND) == []
    assert from_deadline(ROUND | {"d_day": 0, "attendance_required": True}) == []


def test_missing_needs_every_token_group() -> None:
    (same_day,) = [o for o in from_round(ROUND, "round") if o.key.startswith("round:same_day")]

    # "하루 1건"은 말했지만 "다른 날"이 없으면 덧붙입니다(골든셋 P-063).
    assert missing([same_day], "12월 8일은 하루 1건만 인정돼요.") == [same_day]
    assert missing([same_day], "같은 날은 1건이라 다른 날 해 주세요.") == []


def test_prompt_block_lists_duties_and_is_empty_without_them() -> None:
    duties = from_round(ROUND, "round")

    assert prompt_block(duties).startswith("## 반드시 답에 담을 사실")
    assert prompt_block([]) == ""


@pytest.mark.parametrize(
    ("kind", "group", "round_no", "used", "status"),
    [
        # 골든셋 P-013·P-091: 반복수급자 3차부터 구직활동만
        ("lecture", "repeat", 3, LimitsUsed(), ActivityStatus.NOT_ALLOWED),
        # 일반 8차부터 구직활동만(ACT-030)
        ("lecture", "general", 8, LimitsUsed(), ActivityStatus.NOT_ALLOWED),
        # 취업특강은 수급 기간 전체 2회까지 (골든셋 P-011·P-012)
        ("lecture", "general", 4, LimitsUsed(lecture=2), ActivityStatus.LIMIT_OVER),
        ("lecture", "general", 4, LimitsUsed(lecture=1), None),
        ("job_application", "repeat", 5, LimitsUsed(), None),
        # 일반 수급자 자원봉사는 인정 안 됨 (골든셋 P-021)
        ("volunteer", "general", 2, LimitsUsed(), ActivityStatus.NOT_ALLOWED),
        ("no_such_kind", "general", 2, LimitsUsed(), None),
    ],
)
def test_admission_before_recording(
    kind: str, group: str, round_no: int, used: LimitsUsed, status: ActivityStatus | None
) -> None:
    verdict = admission(kind, group, round_no, used)

    assert verdict.status == status
    if status is not None:
        assert verdict.message and verdict.rule_refs


def test_job_search_only_round_says_so() -> None:
    verdict = admission("lecture", "repeat", 3, LimitsUsed())

    assert verdict.message is not None
    assert "구직활동" in verdict.message and "인정되지 않아요" in verdict.message


def test_tool_result_duties_for_refused_and_planned_activity() -> None:
    refused = {
        "recorded": False,
        "admission": {
            "kind": "lecture",
            "status": "limit_over",
            "message": "취업특강은 수급 기간 전체에서 2번까지만 인정돼요.",
            "rule_refs": ["ACT-043"],
            "limit_max": 2,
        },
    }
    planned = {"recorded": True, "planned": True, "activity_date": "2026-12-18"}

    (limit,) = from_tool_result("record_activity", refused)
    (later,) = from_tool_result("record_activity", planned)

    assert limit.satisfied_by("특강은 2회까지예요")
    assert "12월 18일(금)" in later.text and later.satisfied_by("예정으로 넣었어요")
    assert from_tool_result("check_round", refused) == []


def _finish(
    monkeypatch: pytest.MonkeyPatch, answer: str, duties: list[Obligation]
) -> tuple[list, dict]:
    events: list = []
    monkeypatch.setattr(finish_node, "emit", events.append)
    state = {
        "messages": [HumanMessage("다 했죠?"), AIMessage(answer)],
        "obligations": [d.as_state() for d in duties],
        "cited": [],
        "facts": {},
    }
    return events, finish_node.finish(state)


def test_finish_appends_only_missing_duties_and_cites_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duties = from_deadline(ROUND | {"d_day": 0, "now_time": "17:20"})

    events, result = _finish(monkeypatch, "네, 지금 보내시면 돼요.", duties)

    tokens = [e.text for e in events if isinstance(e, TokenEvent)]
    done = next(e for e in events if isinstance(e, DoneEvent))
    assert tokens == ["\n\n" + duties[0].text]
    assert result["messages"][0].text == duties[0].text
    assert "DUE-093" in done.rule_refs


def test_finish_adds_nothing_when_answer_already_has_the_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duties = from_deadline(ROUND | {"d_day": 0, "now_time": "16:50"})

    events, result = _finish(monkeypatch, "오늘 17시까지 고용24에서 보내세요.", duties)

    assert not [e for e in events if isinstance(e, TokenEvent)]
    assert result == {}


@pytest.mark.parametrize(
    ("scope", "said", "ok"),
    [
        ("out_of_scope", "국민연금공단에 물어보세요", False),
        ("out_of_scope", "고용노동부 고객상담센터(1350)에 확인해 주세요", True),
        ("privacy", "사진은 읽은 뒤 삭제해요. 내 정보 화면에서 지울 수 있어요", True),
        ("privacy", "사진은 저장하지 않아요", False),  # 골든셋 M-015·M-035
    ],
)
def test_scope_duty(scope: str, said: str, ok: bool) -> None:
    (duty,) = from_scope(scope)

    assert duty.satisfied_by(said) is ok


def test_scope_in_scope_has_no_duty() -> None:
    assert from_scope("in_scope") == [] and from_scope(None) == []


def test_pii_duties_by_kind() -> None:
    # 골든셋 M-002·M-004·M-022: "저장하지 않음 + 내 정보 화면", M-036~039: 고용24 선택지
    duties = from_pii(["phone", "sensitive"])

    assert _keys(duties) == ["pii:profile", "pii:sensitive"]
    assert duties[0].satisfied_by("저장하지 않아요. 내 정보 화면에서 관리해요")
    assert not duties[0].satisfied_by("번호는 빼고 다시 말씀해 주세요")


def test_same_day_reason_without_other_day_when_round_is_already_full() -> None:
    # 건수를 다 채운 회차에서는 "다른 날 더 하라"를 요구하지 않습니다(같은 안내가 두 번 붙던 문제).
    full = ROUND | {"remaining": 0, "remaining_job_search": 0, "interval_days": None}
    (same_day,) = [o for o in from_round(full, "round") if o.key.startswith("round:same_day")]

    assert same_day.satisfied_by("12월 8일 2건은 같은 날이라 1건만 인정돼요.")
    assert "다른 날" not in same_day.text
