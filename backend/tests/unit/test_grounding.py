"""답의 근거 검사(agent/grounding.py)와 근거 줄 고르기(nodes/finish.py)."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent import grounding
from app.agent.grounding import Evidence, SentenceChecker, claims
from app.agent.nodes.finish import done_event
from app.agent.output import CHECK_NOTE, SentenceStream

RULE = {"id": "DUE-093", "내용": "17시까지 전송 못하면 당일 18시까지 센터에 출석해 신청한다."}
FACTS = {"round": {"remaining": 1, "recognition_date": "2026-12-22"}, "rules": [RULE]}
GUIDE = {"제목": "조기재취업수당", "내용": "남은 일수의 절반", "출처": "고용24 「조기재취업수당」"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("일 상한 68,100원", {"68100원"}),
        ("1,680만원 이하", {"16800000원"}),
        ("12월 22일까지 1건 더", {"12-22", "1건"}),
        ("오후 6시까지, 17:00 전", {"18시", "17시"}),
        ("2025년 8월 퇴사", {"2025-8"}),
        ("4주에 2회, 학점 3.8", {"4주", "2회"}),
        ("1. 이력서 쓰기", set()),
    ],
)
def test_claims_normalize_numbers_with_units(text: str, expected: set[str]) -> None:
    assert claims(text) == expected


def test_evidence_accepts_facts_tool_results_and_user_words_but_not_past_answers() -> None:
    messages = [
        HumanMessage("4차 출석은 몇 시까지예요?"),
        AIMessage("예전 답: 15시까지예요."),
        ToolMessage(content='{"required": 2}', tool_call_id="t1"),
    ]
    evidence = Evidence.of_turn(FACTS, messages)

    assert evidence.ungrounded("12월 22일까지 1건 더 하면 돼요.") == []
    assert evidence.ungrounded("4차는 2건이 필요해요.") == []  # 사용자 말·도구 결과
    assert evidence.ungrounded("15시까지 가세요.") == ["15시"]  # 모델의 예전 답은 근거가 아님


def test_risky_sentence_is_checked_by_model_and_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []
    monkeypatch.setattr(
        grounding, "supported_by_model", lambda s, e: asked.append(s) or "인정" in s
    )
    check = SentenceChecker(Evidence.of_turn(FACTS, []))

    assert check("면접은 구직활동으로 인정돼요.")
    assert not check("그러면 실업급여를 받을 수 있어요.")
    assert check("받을 수 없어요.")  # 한 답에 두 번까지만 묻습니다
    assert len(asked) == 2


def test_stream_removes_ungrounded_sentence_and_adds_note() -> None:
    check = SentenceChecker(Evidence.of_turn(FACTS, []))
    stream = SentenceStream(check=check)

    sent = stream.feed("12월 22일까지 1건 더 필요해요. 하루 68,100원 나와요.\n") + stream.close()

    assert "".join(sent) == stream.text
    assert "68,100원" not in stream.text
    assert stream.text.startswith("12월 22일까지 1건 더 필요해요.")
    assert stream.text.endswith(CHECK_NOTE)


def _state(answer: str) -> dict:
    return {
        "messages": [AIMessage(answer)],
        "attached": ["DUE-093"],
        "facts": {"stage": "recognition", "guides": [GUIDE]},
    }


def test_cite_keeps_only_attached_cards_used_in_answer() -> None:
    used = done_event(_state("오늘 17시까지 못 보내면 18시까지 센터에 가서 신청하세요."))
    unused = done_event(_state("희망 지역을 인천으로 저장했어요."))

    assert used.cite == "취업드림수첩(2025년판 PDF)"
    assert used.rule_refs == ["DUE-093"]
    assert unused.cite is None


def test_cite_includes_guide_source_only_when_used() -> None:
    done = done_event(_state("조기재취업수당은 남은 일수의 절반을 받을 수 있어요."))

    assert done.cite == "고용24 「조기재취업수당」"


def test_cite_includes_rules_behind_round_numbers_and_steps_used_in_answer() -> None:
    round_ = {"recognition_date": "2026-12-22", "remaining": 1, "rule_refs": ["ACT-023"]}
    steps = {"text": "…", "rule_refs": ["PROC-009", "PROC-010"]}
    facts = {"stage": "recognition", "round": round_, "procedure_steps": steps}

    def cite_of(answer: str) -> list[str]:
        return done_event({"messages": [AIMessage(answer)], "facts": facts}).rule_refs

    assert cite_of("12월 22일까지 1건만 더 하면 돼요.") == ["ACT-023"]
    assert cite_of("구직등록, 온라인 교육, 수급자격 신청, 실업인정 순서예요.") == [
        "PROC-009",
        "PROC-010",
    ]
    assert cite_of("인천으로 저장했어요.") == []


def test_cite_reads_whole_turn_and_paraphrased_card_body() -> None:
    messages = [
        HumanMessage("취업특강 들은 것도 넣어 주세요"),
        AIMessage("반복수급자는 3차부터 구직활동만 인정돼요."),
        AIMessage("대신 입사지원을 해 보세요."),  # 도구 뒤 마무리 글
    ]
    state = {"messages": messages, "attached": ["ACT-104"], "facts": {}}

    assert done_event(state).rule_refs == ["ACT-104"]


def test_form_panel_cites_only_named_rules_not_number_overlap() -> None:
    round_ = {"recognition_date": "2026-12-22", "remaining": 1, "rule_refs": ["ACT-023"]}
    facts = {"stage": "recognition", "round": round_}

    def cite_of(answer: str, panel: str) -> list[str]:
        state = {"messages": [AIMessage(answer)], "facts": facts, "panel": panel}
        return done_event(state | {"attached": ["DUE-093"]}).rule_refs

    # 이력서에 적은 날짜·건수가 회차 값과 겹쳐도 근거 줄을 붙이지 않습니다.
    assert cite_of("퇴사일을 12월 22일로 적었어요. 경력 1건을 넣었어요.", "resume") == []
    assert cite_of("12월 22일까지 1건만 더 하면 돼요.", "round") == ["ACT-023"]
