"""패널 안의 제한된 도구 루프: call_model ⇄ run_tools, 되묻기는 ask(interrupt).

- 모델에는 그 패널 도구(registry.TOOLS_BY_PANEL)와 ask_user만 보입니다(도구 제한, ADR 0001).
- 숫자·저장은 도구(규칙 함수)가 하고 모델은 고르고 말만 합니다.
- 한 턴 호출 상한(MAX_MODEL_CALLS, MAX_TOOL_CALLS)을 넘으면 루프를 멈춥니다.
- ask_user는 두 노드로 나눕니다. interrupt된 노드는 재개할 때 처음부터 다시 실행되므로,
  질문 이벤트는 앞 노드(run_tools)에서 한 번만 내고 ask 노드는 interrupt만 합니다.
"""

import json
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field, ValidationError

from app.agent import gateway
from app.agent.events import emit
from app.agent.graph import AgentState, tool_context_of
from app.agent.prompts import load_prompt
from app.agent.tools.registry import TOOLS, TOOLS_BY_PANEL, ToolError, run_tool
from app.schemas.common import FormUpdate
from app.schemas.messages import AskUserEvent, TokenEvent, ToolCallEvent

MAX_MODEL_CALLS = 4  # 분류 1 + 패널 루프 3 (노션 「에이전트 구조 설계」 8절)
MAX_TOOL_CALLS = 6
ASK_USER = "ask_user"
BASE_PROMPT = "panels/base"


class AskUserInput(BaseModel):
    """사용자에게 하나만 묻습니다. 고를 수 있으면 choices를 줍니다(버튼으로 보임)."""

    question: str = Field(description="한 문장 질문. 쉬운 말로")
    choices: list[str] = Field(
        default_factory=list, max_length=4, description="선택지(없으면 빈 목록)"
    )


def _tool_schema(name: str, description: str, model: type[BaseModel]) -> dict[str, Any]:
    schema = convert_to_openai_tool(model)
    schema["function"].update(name=name, description=description)
    return schema


def tool_schemas(panel: str) -> list[dict[str, Any]]:
    schemas = [
        _tool_schema(t.name, t.description, t.input_model)
        for t in (TOOLS[name] for name in TOOLS_BY_PANEL[panel])
    ]
    schemas.append(_tool_schema(ASK_USER, "사용자에게 하나 되묻기", AskUserInput))
    return schemas


def system_prompt(state: AgentState) -> str:
    facts = json.dumps(state.get("facts", {}), ensure_ascii=False)
    panel = state["panel"]
    return "\n\n".join(
        [
            load_prompt(BASE_PROMPT),
            load_prompt(f"panels/{panel}"),
            f"## 지금 상황 (DB 기준, 그대로 옮기고 계산하지 않음)\n{facts}",
        ]
    )


def call_model(state: AgentState) -> dict[str, Any]:
    model = gateway.get_chat_model("agent").bind_tools(tool_schemas(state["panel"]))
    messages = [SystemMessage(system_prompt(state)), *state["messages"]]
    reply: AIMessageChunk | None = None
    for chunk in model.stream(messages):
        if chunk.text:
            emit(TokenEvent(text=chunk.text))
        reply = chunk if reply is None else reply + chunk
    message = AIMessage(
        content=reply.text if reply else "",
        tool_calls=reply.tool_calls if reply else [],
    )
    return {"messages": [message], "model_calls": state.get("model_calls", 0) + 1}


def _last_ai(state: AgentState) -> AIMessage:
    message = state["messages"][-1]
    assert isinstance(message, AIMessage)
    return message


def after_model(state: AgentState) -> str:
    return "run_tools" if _last_ai(state).tool_calls else "finish"


def _run_one(state: AgentState, config: RunnableConfig, name: str, args: dict[str, Any]) -> str:
    ctx = tool_context_of(config)
    if name not in TOOLS_BY_PANEL[state["panel"]]:
        return "이 단계에서 쓸 수 없는 도구예요."
    if ctx is None:
        return "지금은 도구를 쓸 수 없어요."
    emit(ToolCallEvent(name=name, status="started"))
    try:
        result = run_tool(ctx, name, args)
    except (ToolError, ValidationError) as exc:
        return (
            f"도구를 쓰지 못했어요: {exc if isinstance(exc, ToolError) else '인자가 맞지 않아요'}"
        )
    finally:
        emit(ToolCallEvent(name=name, status="finished"))
    for update in result.get("updates", []):
        emit(FormUpdate.model_validate(update))
    return json.dumps(result, ensure_ascii=False, default=str)


def run_tools(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """ask_user가 아닌 도구를 실행합니다. ask_user가 있으면 질문 이벤트만 내고 ask로 넘깁니다."""
    calls = _last_ai(state).tool_calls
    used = state.get("tool_calls", 0)
    results = []
    for call in calls:
        if call["name"] == ASK_USER:
            continue
        used += 1
        content = (
            "이번 턴 도구 호출 상한에 걸려 실행하지 않았어요."
            if used > MAX_TOOL_CALLS
            else _run_one(state, config, call["name"], call["args"])
        )
        results.append(ToolMessage(content=content, tool_call_id=call["id"]))
    asks = [c for c in calls if c["name"] == ASK_USER]
    if asks:
        ask = AskUserInput.model_validate(asks[0]["args"])
        emit(AskUserEvent(question_id=asks[0]["id"], text=ask.question, choices=ask.choices))
        # 두 번째 질문부터는 한 번에 하나만 묻도록 돌려보냅니다.
        results.extend(
            ToolMessage(content="한 번에 하나만 물어요.", tool_call_id=c["id"]) for c in asks[1:]
        )
    return {"messages": results, "tool_calls": used}


def after_tools(state: AgentState) -> str:
    if any(c["name"] == ASK_USER for c in _last_ai_with_calls(state).tool_calls):
        return "ask"
    return "call_model" if state.get("model_calls", 0) < MAX_MODEL_CALLS else "finish"


def _last_ai_with_calls(state: AgentState) -> AIMessage:
    return next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))


def ask(state: AgentState) -> dict[str, Any]:
    """그래프를 멈춥니다. 응답기가 `Command(resume=가린 답)`으로 재개하면 그 답을 모델에 넘깁니다.

    답이 질문과 관계없는 말(딴소리)이면 모델이 그렇게 판단해 새 주제로 넘어갑니다(패널 프롬프트).
    """
    call = next(c for c in _last_ai_with_calls(state).tool_calls if c["name"] == ASK_USER)
    answer = interrupt({"question_id": call["id"]})
    return {"messages": [ToolMessage(content=f"사용자 답: {answer}", tool_call_id=call["id"])]}
