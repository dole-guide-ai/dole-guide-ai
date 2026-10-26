"""ask 노드: 다음 질문을 화면에 보냅니다 (노션 「AI 설계」 2-1).

질문은 이번 턴에 칸이 바뀐 뒤 규칙 함수로 다시 고릅니다. 문구 · 선택지는 템플릿에서 만들고
(questions.py), LLM이 만들지 않습니다. 질문이 없으면(활동 기록 · 교육) 보내지 않습니다.

그래프는 여기서 끝납니다. 다음 메시지는 새 턴으로 시작하고, 직전 질문은 체크포인트의
`question`에 남아 라우터 · 고정 경로가 씁니다. (interrupt로 멈추지 않는 이유: 노션 9절 결정 기록)
"""

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent.events import emit
from app.agent.graph_config import tool_context_of
from app.agent.nodes.context import next_question
from app.agent.panels import Panel
from app.agent.state import AgentState
from app.schemas.messages import AskUserEvent


def ask(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    ctx = tool_context_of(config)
    panel = state.get("panel")
    if ctx is None or panel is None:
        return {"question": None}
    question = next_question(ctx, Panel(panel), state.get("doc_failed", False))
    if question:
        emit(
            AskUserEvent(
                question_id=question["id"],
                text=question["text"],
                choices=question.get("choices", []),
                accepts_file=question["id"] in FILE_QUESTIONS,
            )
        )
    return {"question": question}


# 사진 · 서류를 올려 답할 수 있는 질문
FILE_QUESTIONS = frozenset({"resume.doc_retry", "resume.career_new", "resume.license"})
