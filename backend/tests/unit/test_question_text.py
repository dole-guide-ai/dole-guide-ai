"""이력서 질문 문구(rules/question_text): 변수가 비어도 대명사를 쓰지 않습니다."""

import re

import pytest

from app.rules.question_text import question_choices, question_text, templates
from app.rules.resume import ResumeQuestion

PRONOUN = re.compile(r"그곳|거기|그분|그것|이것|저것|그때")


def test_fills_company_name() -> None:
    q = ResumeQuestion("resume.career_duties", {"company": "한빛물류"})
    assert question_text(q).startswith("한빛물류에서는 주로 어떤 일을 하셨어요?")


@pytest.mark.parametrize("question_id", sorted(templates()["questions"]))
def test_no_pronoun_even_when_vars_are_missing(question_id: str) -> None:
    for vars_ in ({}, {"company": None, "year": None, "level": None, "occupation": None}):
        text = question_text(ResumeQuestion(question_id, vars_))
        assert text and "{" not in text and not PRONOUN.search(text), text


def test_unnamed_and_fallback_wording() -> None:
    assert question_text(ResumeQuestion("resume.career_period")).startswith(
        "최근에 다니신 회사에는"
    )
    end_check = ResumeQuestion("resume.career_end_check", {"year": 2026, "month": 9})
    assert question_text(end_check) == "최근에 다니신 회사 퇴사가 2026년 9월이 맞나요?"


def test_confirm_is_not_asked_in_chat_and_choices_come_from_rules_or_template() -> None:
    assert question_text(ResumeQuestion("resume.value_confirm")) is None
    assert question_choices(ResumeQuestion("resume.license", choices=("있어요", "없어요"))) == [
        "있어요",
        "없어요",
    ]
    assert question_choices(ResumeQuestion("resume.career_more")) == ["네, 있어요", "없어요"]
