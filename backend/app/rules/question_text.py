"""이력서 다음 질문(ResumeQuestion) → 화면에 보일 질문 문장. LLM 없음.

문구는 `data/templates/resume_questions.json`에 두고, 여기서는 문구 변수만 채웁니다
(rules/entry_text와 같은 방식). 질문 문장을 모델이 만들지 않으므로 같은 질문이 답 글과
질문 카드에 두 번 나오거나 순서가 흔들리지 않습니다.
"""

import json
from functools import cache
from pathlib import Path
from string import Formatter
from typing import Any

from app.rules.resume import ResumeQuestion

TEMPLATES_JSON = (
    Path(__file__).resolve().parents[2] / "data" / "templates" / "resume_questions.json"
)
# 이번 대화에서 한 번만 묻는 질문(첫 경력 뒤 그 전 경력). 규칙 표 밖이라 여기서 정합니다.
CAREER_MORE = "resume.career_more"


@cache
def templates() -> dict[str, Any]:
    return json.loads(TEMPLATES_JSON.read_text(encoding="utf-8"))


def question_text(q: ResumeQuestion) -> str | None:
    """템플릿이 없는 질문(예: 바꾼 값 확인)은 None. 대화에서 묻지 않습니다.

    문구 변수(회사 이름 등)가 비면 대명사("그곳")로 메우지 않고, 이름 없이 쓴 문구(unnamed)나
    변수별 설명 이름(fallbacks, 예: "최근에 다니신 회사")을 씁니다.
    """
    t = templates()
    template = t["questions"].get(q.id)
    if template is None:
        return None
    names = {name for _, name, _, _ in Formatter().parse(template) if name}
    values = {k: v for k, v in q.vars.items() if v not in (None, "")}
    missing = names - values.keys()
    if missing and q.id in t["unnamed"]:
        return t["unnamed"][q.id]
    return template.format(**{**{n: t["fallbacks"].get(n, "") for n in missing}, **values})


def question_choices(q: ResumeQuestion) -> list[str]:
    return list(q.choices) or list(templates()["choices"].get(q.id, []))


def career_more(company: str | None) -> ResumeQuestion:
    return ResumeQuestion(CAREER_MORE, {"company": company})
