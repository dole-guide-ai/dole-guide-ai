"""패널 서브그래프 정의 (노션 「AI 설계」 2-2-1).

서브그래프 하나 = 오른쪽 패널 하나. 각자 프롬프트(prompts/<panel>/agent.md), 넘기는 도구,
쓸 수 있는 칸을 가집니다. 무엇을 물을지는 규칙 함수가 정합니다(nodes/context.py).
"""

from enum import StrEnum

from app.agent.tools.registry import TOOLS, TOOLS_BY_PANEL


class Panel(StrEnum):
    RESUME = "resume"
    ROUND = "round"
    APPLICATION = "application"
    EDUCATION = "education"


# 모든 패널이 쓸 수 있는 공용 도구 (RAG 근거 검색, 2-2-2)
COMMON_TOOLS: tuple[str, ...] = ("search_guide",)

# 이력서 서브그래프가 쓸 수 있는 칸 (상태 · 기본정보는 도구로 쓰지 않음)
RESUME_PATHS: tuple[str, ...] = (
    "/resume_title",
    "/education",
    "/job_preferences",
    "/careers",
    "/careers_status",
    "/certifications",
    "/certifications_status",
    "/other_certifications",
    "/competencies",
    "/competencies_status",
    "/additional_info",
)


def tools_for(panel: Panel) -> tuple[str, ...]:
    return TOOLS_BY_PANEL[panel] + tuple(t for t in COMMON_TOOLS if t in TOOLS)


def prompt_name(panel: Panel) -> str:
    return f"{panel}/agent"
