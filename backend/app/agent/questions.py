"""질문 ID를 화면 질문(ask_user)으로 바꿉니다.

질문 ID와 문구 변수는 규칙 함수(app/rules)가 정하고, 문구는 data/templates/questions.json에서만
만듭니다. LLM은 질문 문구를 만들지 않습니다(질문 하나 · 선택지 3개 이하, 상세기획 2-0.2).
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.agent.state import Question
from app.rules.answers import ApplicationQuestion
from app.rules.resume import ResumeQuestion

TEMPLATES = Path(__file__).resolve().parents[2] / "data" / "templates" / "questions.json"
MAX_CHOICES = 3
UNKNOWN_VAR = "그곳"


@lru_cache(maxsize=1)
def _templates() -> dict[str, Any]:
    return json.loads(TEMPLATES.read_text(encoding="utf-8"))


class _Vars(dict):
    """문구 변수가 비면 어색한 None 대신 자리말을 씁니다."""

    def __missing__(self, key: str) -> str:
        return UNKNOWN_VAR


def resume_question(q: ResumeQuestion) -> Question:
    text = _templates()["resume"][q.id]
    filled = {k: (UNKNOWN_VAR if v is None else v) for k, v in q.vars.items()}
    return Question(
        id=q.id,
        text=text.format_map(_Vars(filled)),
        choices=list(q.choices)[:MAX_CHOICES],
        values={},
        path=q.vars.get("path"),
    )


def application_question(q: ApplicationQuestion) -> Question:
    template = _templates()["application"][q.id]
    pairs = template["choices"][:MAX_CHOICES]
    return Question(
        id=q.id,
        text=template["text"],
        choices=[label for label, _ in pairs],
        values={label: value for label, value in pairs},
        path=q.path,
    )
