"""그래프 상태 (노션 「AI 설계」 2-3).

체크포인트에 저장되므로 JSON으로 바꿀 수 있는 값만 둡니다. 개인정보 컬럼(user_profiles)과 DB 세션은
넣지 않습니다(턴 정보·도구 문맥은 config로 받음). 턴마다 새로 쓰는 값은 preprocess가 비웁니다.
"""

from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class Question(TypedDict, total=False):
    """화면에 보낼 질문 하나 (ask_user). 문구·선택지는 data/templates/questions.json."""

    id: str
    text: str
    choices: list[str]
    # 선택지 글자 → 저장 값 (신청서 본인 답변 칸)
    values: dict[str, str]
    # 이 질문이 다루는 칸 (도구 쓰기 제한, 신청서 칸 경로)
    path: str | None


class AgentState(TypedDict, total=False):
    # 대화 기록: 사용자 말(가린 글)과 AI 답만. 도구 왕복은 scratch에 둡니다.
    messages: Annotated[list[AnyMessage], add_messages]

    # ── 계정 단위로 이어지는 값
    panel: str | None
    question: Question | None
    # 같은 질문을 다시 물은 횟수 (lookup_code 세 번 실패 등)
    retry_count: int

    # ── 턴마다 새로 쓰는 값
    text: str  # 이번 사용자 말 (개인정보 가린 글)
    attachments: list[str]  # 판독한 서류 글 (가린 글)
    doc_failed: bool
    blocked: bool  # 입력 가드가 막음
    notes: list[str]  # 답 앞에 붙일 고정 안내 (개인정보를 가렸다 등)
    scratch: list[AnyMessage]  # 이번 턴 agent ⇄ tools 왕복
    rounds: int  # 이번 턴 도구 바퀴 수
    facts: list[str]  # 도구 결과 글 (verify가 숫자·날짜를 대조)
    sources: list[dict[str, Any]]  # search_guide 결과 청크
    reply: str | None  # verify 전 답 문장
    fixed: bool  # 고정 경로(LLM 없이 만든 답) — verify를 건너뜀
    cite: list[dict[str, Any]]
    rule_refs: list[str]
