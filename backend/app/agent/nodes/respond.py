import json
import re

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import ValidationError

from app.agent import gateway
from app.agent.prompts import load_prompt
from app.agent.schemas import AgentOutput, AgentState

# 모델에 보내는 상태값. 화면 시연용 시각(demo_time)처럼 답에 필요 없는 값은 뺍니다.
STATE_KEYS = (
    "age_at_separation",
    "has_disability",
    "recipient_type",
    "stage",
    "resume_status",
    "education_done",
    "eligibility_applied_date",
    "completed_rounds",
    "next_recognition_date",
)
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")
FALLBACK_REPLY = "죄송해요, 답을 정리하지 못했어요. 한 번만 다시 말씀해 주세요."


def respond(state: AgentState) -> AgentState:
    """모델 한 번 호출로 의도 파악·서류 값 뽑기·답 쓰기를 합니다 (최소 버전)."""
    # JSON 모드: 모델이 JSON 한 덩어리만 내도록 합니다. 칸 검사는 parse_output이 합니다.
    model = gateway.get_chat_model("agent").bind(response_format={"type": "json_object"})
    response = model.invoke(_messages(state))
    return {"output": parse_output(str(response.content))}


def _messages(state: AgentState) -> list[BaseMessage]:
    context = {
        **state["situation"],
        "state": {key: state["state"].get(key) for key in STATE_KEYS},
        "resume": state["data"]["resume"],
    }
    messages: list[BaseMessage] = [
        SystemMessage(load_prompt("respond")),
        SystemMessage("## 상황\n" + json.dumps(context, ensure_ascii=False)),
    ]
    for turn in state.get("history", []):
        if turn["role"] == "user":
            messages.append(HumanMessage(_wrap(turn["text"])))
        else:
            messages.append(AIMessage(turn["text"]))
    messages.append(HumanMessage(_wrap(state["message"])))
    return messages


def _wrap(text: str) -> str:
    """사용자 말을 표시로 감싸 지시와 섞이지 않게 합니다 (프롬프트 공격 방어)."""
    return f"<user_message>\n{text}\n</user_message>"


def parse_output(text: str) -> AgentOutput:
    """JSON을 칸에 맞춰 읽습니다. 모양이 틀리면 서류는 건드리지 않고 다시 말해 달라고 답합니다."""
    raw = FENCE.sub("", text.strip())
    try:
        return AgentOutput.model_validate_json(raw)
    except ValidationError:
        return AgentOutput(reply=FALLBACK_REPLY)
