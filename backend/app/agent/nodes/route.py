"""이번 말을 어느 패널이 맡을지 정합니다(노션 「에이전트 구조 설계」 6절).

절차 순서는 법규가 정하므로 경로는 코드(규칙)가 보장합니다.
규칙이 하나로 정하지 못할 때만 작은 LLM 분류를 부릅니다.
"""

import re
from enum import StrEnum
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agent import gateway
from app.agent.graph import AgentState
from app.agent.prompts import load_prompt
from app.schemas.procedure import Stage


class Panel(StrEnum):
    RESUME = "resume"
    ROUND = "round"
    APPLICATION = "application"
    GUIDE = "guide"


# 제도를 묻는 말: 의문형 끝 + 제도 단어, 내 서류를 다루는 단어 없음
# 물음표나 의문 어미로 끝나는 말. "~요"만으로는 판단하지 않습니다("땄어요"는 평서문).
_QUESTION_END = re.compile(r"(\?|나요|까요|가요|죠|는지|ㄹ까|되나|됩니까|있나|없나)\s*$")
# "돼요"·"되나요" 같은 흔한 의문 어미는 넣지 않습니다(회차 질문 "몇 번 해야 돼요"도 걸림).
_POLICY_WORDS = re.compile(
    r"실업급여|구직급여|수급|자격(?!증)|받을 수|받나요|신고|연기|연장|"
    r"내일배움|국민취업|조기재취업|실업크레딧|해외|여행|사업자"
)
_MY_FORM_WORDS = re.compile(r"이력서|신청서|넣어|써 ?주|적어|기록|저장|올려")
_ROUND_WORDS = re.compile(
    r"지원했|입사 ?지원|지원 ?완료|지원서|면접|넣었|활동|회차|몇 ?번|몇 ?건|몇개|특강|박람회|"
    r"추천|채워|모자라|부족"
)
# preprocess가 첨부에서 읽은 글을 감싸는 표시. 단어 규칙은 사용자가 직접 한 말만 봅니다.
_ATTACHMENT_START = "<첨부>"
_APPLICATION_WORDS = re.compile(r"신청서|본인 ?답|소득|알바했|일했|취업했|취직했|일당")
_RESUME_WORDS = re.compile(
    r"이력서|경력|다녔|일했어요|그만뒀|들어가|입사|퇴사|학교|졸업|자격증|희망|직종|지역|불러오"
)

CLASSIFY_PROMPT = "router/classify"


class RouteChoice(BaseModel):
    panel: Panel


def by_rules(text: str, stage: str | None) -> Panel | None:
    """규칙으로 정하면 패널, 못 정하면 None(LLM 분류로).

    첨부에서 읽은 글(서류 속 "입사"·"경력" 같은 단어)은 단어 규칙에 쓰지 않습니다. 실업인정
    단계에서 올린 첨부는 구직활동 증빙이므로, 신청서 쪽 말이 아니면 회차 패널로 보냅니다.
    """
    text, attached, _ = text.partition(_ATTACHMENT_START)
    if stage == Stage.RECOGNITION and attached and not _APPLICATION_WORDS.search(text):
        return Panel.ROUND
    if (
        _QUESTION_END.search(text)
        and _POLICY_WORDS.search(text)
        and not _MY_FORM_WORDS.search(text)
    ):
        return Panel.GUIDE
    if stage == Stage.JOB_REGISTRATION or (stage is None and _RESUME_WORDS.search(text)):
        return Panel.RESUME
    if stage in (Stage.EDUCATION, Stage.ELIGIBILITY_APPLICATION, Stage.ELIGIBILITY_APPLIED):
        return Panel.RESUME if _RESUME_WORDS.search(text) else Panel.GUIDE
    if stage == Stage.RECOGNITION:
        round_hit = bool(_ROUND_WORDS.search(text))
        application_hit = bool(_APPLICATION_WORDS.search(text))
        if round_hit != application_hit:
            return Panel.ROUND if round_hit else Panel.APPLICATION
        if _RESUME_WORDS.search(text) and not (round_hit or application_hit):
            return Panel.RESUME
    return None


def by_model(text: str, facts: dict[str, Any]) -> Panel:
    model = gateway.get_chat_model("agent").with_structured_output(RouteChoice)
    choice = model.invoke(
        [
            SystemMessage(load_prompt(CLASSIFY_PROMPT)),
            HumanMessage(
                f"절차 단계: {facts.get('stage')}\n<user_message>\n{text}\n</user_message>"
            ),
        ]
    )
    return choice.panel


def route_turn(state: AgentState) -> dict[str, Any]:
    text = str(state["messages"][-1].content)
    facts = state.get("facts", {})
    panel = by_rules(text, facts.get("stage"))
    calls = state.get("model_calls", 0)
    if panel is None:
        panel = by_model(text, facts)
        calls += 1
    return {"panel": panel.value, "model_calls": calls}
