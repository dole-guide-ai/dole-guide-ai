"""코드가 처리하는 선택지 답(nodes/next_question): 버튼 답이 맞는 칸·값으로 저장되는지."""

from langchain_core.messages import HumanMessage

from app.agent.nodes.next_question import FIXED_ANSWERS, NEGOTIABLE_SALARY, fixed_answer_of
from app.rules.resume import suggest_resume_title
from app.schemas.forms.resume import ResumeData

DATA = ResumeData.model_validate(
    {
        "careers": [
            {
                "item_id": "c1",
                "company_name": {"value": "OO물류"},
                "start_date": {"value": "2012-03"},
                "occupation": {"value": {"code": None, "name": "물류"}},
            }
        ],
        "job_preferences": {
            "desired_occupations": [
                {"item_id": "o1", "occupation": {"value": {"code": None, "name": "물류"}}}
            ]
        },
    }
)


def writes(question_id: str, answer: str, vars_: dict | None = None) -> dict:
    fixed = FIXED_ANSWERS[(question_id, answer)]
    return {w.path: (w.value, w.status) for w in fixed.writes(DATA, vars_ or {})}


def test_choice_answers_write_the_matching_field() -> None:
    assert writes("resume.wish_employment", "상관없어요") == {
        "/job_preferences/employment_contract_type": ("관계없음", "confirmed")
    }
    assert (
        writes("resume.wish_military", "네, 맞아요")["/job_preferences/military_alternative"][0]
        == "해당 없음"
    )
    assert (
        writes("resume.wish_wage", "면접 후 결정할게요")["/job_preferences/desired_salary"][0]
        == NEGOTIABLE_SALARY
    )
    exp = writes("resume.wish_experience", "아니요", {"occupation": "물류"})
    assert exp == {"/job_preferences/desired_occupations/o1/experience_type": ("신입", "confirmed")}
    assert writes("resume.career_position", "없었어요", {"company": "OO물류"}) == {
        "/careers/c1/position": ("없음", "confirmed")
    }
    assert writes("resume.license", "없어요")["/certifications_status"][1] == "not_applicable"


def test_title_uses_the_suggestion_shown_in_the_question() -> None:
    assert suggest_resume_title(DATA) == "물류 경력 이력서"
    assert writes("resume.resume_title", "네, 좋아요", {"title": "물류 경력 이력서"}) == {
        "/resume_title": ("물류 경력 이력서", "confirmed")
    }


def test_answer_matching_ignores_spaces_and_punctuation() -> None:
    state = {
        "pending_question": {"id": "resume.career_position", "vars": {}},
        "messages": [HumanMessage("없었어요.")],
    }
    assert fixed_answer_of(state) is FIXED_ANSWERS[("resume.career_position", "없었어요")]
    state["messages"] = [HumanMessage("직급은 반장이었어요")]
    assert fixed_answer_of(state) is None
