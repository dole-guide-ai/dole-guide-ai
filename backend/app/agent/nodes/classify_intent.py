import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.agent import gateway
from app.agent.prompts import load_prompt
from app.agent.schemas import AgentState
from app.core.config import get_settings

RULE_QUESTION = "rule_question"
OTHER = "other"
INTENTS = {RULE_QUESTION, "report", OTHER}
# 활동 인정·증빙·한도를 묻는 말에 자주 나오는 단어 (keyword 모드). 문항이 아니라 주제 기준입니다.
RULE_WORDS = re.compile(
    r"증빙|증명서|(?<!실업)인정|활동으로|활동이|특강|학원|봉사|훈련|심리검사|상담|"
    r"뭘 ?내|뭐 ?내|챙겨|가져가|몇 ?번까지|몇 ?회|횟수|한도|확인서|캡처"
)
# 활동을 알려 주는 말("지원했어요")이나 파일을 건네는 말("캡처예요", "읽어 주세요")은
# 규정 질문이 아닙니다.
REPORT_ENDINGS = re.compile(
    r"(했어요|했습니다|봤어요|들었어요|다녀왔어요|넣었어요|이에요|예요|읽어 ?주세요)\s*[.!]?\s*$"
)


def classify_intent(state: AgentState) -> AgentState:
    """이번 말이 활동 규정 질문인지 가립니다. 규정 질문일 때만 규칙 카드를 붙이기 위해서입니다.

    RULE_CARDS_MODE가 keyword면 단어로, llm이면 작은 모델 호출로 가립니다.
    그 밖의 모드에서는 가리지 않습니다.
    """
    mode = get_settings().rule_cards_mode
    message = state["message"]
    if mode == "keyword":
        return {"intent": by_keyword(message)}
    if mode == "llm":
        return {"intent": by_llm(message)}
    return {"intent": OTHER}


def by_keyword(message: str) -> str:
    if REPORT_ENDINGS.search(message):
        return OTHER
    return RULE_QUESTION if RULE_WORDS.search(message) else OTHER


def by_llm(message: str) -> str:
    model = gateway.get_chat_model("agent").bind(response_format={"type": "json_object"})
    response = model.invoke([
        SystemMessage(load_prompt("classify_intent")),
        HumanMessage(f"<user_message>\n{message}\n</user_message>"),
    ])  # fmt: skip
    try:
        intent = json.loads(str(response.content)).get("intent")
    except json.JSONDecodeError, AttributeError:
        return OTHER
    return intent if intent in INTENTS else OTHER
