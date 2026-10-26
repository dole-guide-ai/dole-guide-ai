"""패널 안의 제한된 도구 루프: call_model ⇄ run_tools, 되묻기는 ask(interrupt).

- 모델에는 그 패널 도구(registry.TOOLS_BY_PANEL)와 ask_user만 보입니다(도구 제한, ADR 0001).
- 숫자·저장은 도구(규칙 함수)가 하고 모델은 고르고 말만 합니다.
- 한 턴 호출 상한(MAX_MODEL_CALLS, MAX_TOOL_CALLS)을 넘으면 루프를 멈춥니다.
- ask_user는 두 노드로 나눕니다. interrupt된 노드는 재개할 때 처음부터 다시 실행되므로,
  질문 이벤트는 앞 노드(run_tools)에서 한 번만 내고 ask 노드는 interrupt만 합니다.
"""

import json
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field, ValidationError

from app.agent import gateway
from app.agent.events import emit
from app.agent.graph import AgentState, tool_context_of, turn_of
from app.agent.grounding import Evidence, SentenceChecker
from app.agent.input import images
from app.agent.output import SentenceStream
from app.agent.prompts import load_prompt
from app.agent.tools.registry import TOOLS, TOOLS_BY_PANEL, ToolError, run_tool
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.common import FormUpdate
from app.schemas.messages import AskUserEvent, TokenEvent, ToolCallEvent
from app.services import files as files_service

MAX_MODEL_CALLS = 4  # 분류 1 + 패널 루프 3 (노션 「에이전트 구조 설계」 8절)
MAX_TOOL_CALLS = 6
ASK_USER = "ask_user"
LOOKUP_RULES = "lookup_rules"
PARAGRAPH_GAP = "\n\n"
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


def tool_names(panel: str) -> tuple[str, ...]:
    """패널 도구. 규칙 카드를 미리 붙이는 방식(inject)이면 찾기 도구는 빼서 비교 조건을 맞춥니다."""
    names = TOOLS_BY_PANEL[panel]
    if get_settings().rule_cards_mode == "inject":
        names = tuple(n for n in names if n != LOOKUP_RULES)
    return names


def tool_schemas(panel: str) -> list[dict[str, Any]]:
    schemas = [
        _tool_schema(t.name, t.description, t.input_model)
        for t in (TOOLS[name] for name in tool_names(panel))
    ]
    schemas.append(_tool_schema(ASK_USER, "사용자에게 하나 되묻기", AskUserInput))
    return schemas


def system_prompt(state: AgentState) -> str:
    facts = dict(state.get("facts", {}))
    briefing = "\n".join(f"- {line}" for line in facts.pop("briefing", []))
    panel = state["panel"]
    return "\n\n".join(
        [
            load_prompt(BASE_PROMPT),
            load_prompt(f"panels/{panel}"),
            f"## 지금 상황 (코드가 계산한 사실. 그대로 옮기고 계산하지 않음)\n{briefing}",
            f"## 세부 값·규칙 카드 (DB 기준)\n{json.dumps(facts, ensure_ascii=False)}",
        ]
    )


def _with_images(messages: list[Any], config: RunnableConfig) -> list[Any]:
    """IMAGE_MODE=vision이면 이번 턴 첨부 사진을 마지막 사용자 말에 붙입니다.

    모델에 보내는 복사본에만 붙이고 상태(체크포인트)에는 남기지 않습니다. 사진이 아닌 파일과
    열 수 없는 파일은 보내지 않습니다(문서는 preprocess가 글로 넣음).
    """
    ctx = tool_context_of(config)
    if get_settings().image_mode != "vision" or ctx is None:
        return messages
    file_ids = dict.fromkeys(getattr(turn_of(config), "file_ids", None) or [])
    paths = [
        str(path)
        for file_id in file_ids
        if (path := files_service.open_attachment(ctx.db, ctx.account, file_id))
    ]
    if not (parts := images.image_parts(paths)):
        return messages
    last = next((i for i in range(len(messages) - 1, -1, -1)
                 if isinstance(messages[i], HumanMessage)), None)  # fmt: skip
    if last is None:
        return messages
    patched = HumanMessage([{"type": "text", "text": str(messages[last].content)}, *parts])
    return [*messages[:last], patched, *messages[last + 1 :]]


def call_model(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    model = gateway.get_chat_model("agent").bind_tools(tool_schemas(state["panel"]))
    messages = _with_images([SystemMessage(system_prompt(state)), *state["messages"]], config)
    reply: AIMessageChunk | None = None
    # 문장이 끝날 때마다 걸러서 보냅니다(agent/output.py). 다른 언어가 섞인 문장부터 버리고,
    # 근거에 없는 숫자나 근거를 넘는 단정이 든 문장은 뺍니다(agent/grounding.py).
    check = None
    if get_settings().answer_check:
        check = SentenceChecker(Evidence.of_turn(state.get("facts", {}), state["messages"]))
    sentences = SentenceStream(check=check)
    # 도구를 부르기 전에 이미 말한 글이 있으면 이어지는 글과 붙지 않게 빈 줄을 둡니다.
    gap = PARAGRAPH_GAP if _said_this_turn(state["messages"]) else ""
    for chunk in model.stream(messages):
        for piece in sentences.feed(chunk.text):
            emit(TokenEvent(text=gap + piece))
            gap = ""
        reply = chunk if reply is None else reply + chunk
    for piece in sentences.close():
        emit(TokenEvent(text=piece))
    message = AIMessage(
        content=sentences.text,
        tool_calls=reply.tool_calls if reply else [],
    )
    return {"messages": [message], "model_calls": state.get("model_calls", 0) + 1}


def _said_this_turn(messages: list[Any]) -> bool:
    """이번 턴(마지막 사용자 말 뒤)에 모델이 이미 글을 냈는지."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return False
        if isinstance(message, AIMessage) and message.text:
            return True
    return False


def _last_ai(state: AgentState) -> AIMessage:
    message = state["messages"][-1]
    assert isinstance(message, AIMessage)
    return message


def after_model(state: AgentState) -> str:
    return "run_tools" if _last_ai(state).tool_calls else "finish"


def _failure(exc: Exception) -> str:
    # 서비스 오류(AppError)의 message는 사용자에게 보여도 되는 문구라 모델에 그대로 넘깁니다.
    if isinstance(exc, AppError):
        return f"도구를 쓰지 못했어요: {exc.message}"
    if isinstance(exc, ToolError):
        return f"도구를 쓰지 못했어요: {exc}"
    return "도구를 쓰지 못했어요: 인자가 맞지 않아요"


def _rule_ids(result: dict[str, Any]) -> list[str]:
    """도구 결과에서 근거로 쓸 규칙 ID(규칙 카드 id, 규칙 함수의 rule_refs)를 모읍니다."""
    ids = [r["id"] for r in result.get("rules", [])]
    return ids + list(result.get("rule_refs", []))


def _run_one(
    state: AgentState, config: RunnableConfig, name: str, args: dict[str, Any]
) -> tuple[str, list[str]]:
    """(모델에 돌려줄 결과 글, 근거 규칙 ID). 실패도 예외로 턴을 끝내지 않고 사유로 돌려줍니다."""
    ctx = tool_context_of(config)
    if name not in tool_names(state["panel"]):
        return "이 단계에서 쓸 수 없는 도구예요.", []
    if ctx is None:
        return "지금은 도구를 쓸 수 없어요.", []
    emit(ToolCallEvent(name=name, status="started"))
    try:
        result = run_tool(ctx, name, args)
    except (ToolError, ValidationError, AppError) as exc:
        return _failure(exc), []
    finally:
        emit(ToolCallEvent(name=name, status="finished"))
    for update in result.get("updates", []):
        emit(FormUpdate.model_validate(update))
    return json.dumps(result, ensure_ascii=False, default=str), _rule_ids(result)


def run_tools(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """ask_user가 아닌 도구를 실행합니다. ask_user가 있으면 질문 이벤트만 내고 ask로 넘깁니다."""
    calls = _last_ai(state).tool_calls
    used = state.get("tool_calls", 0)
    cited = list(state.get("cited", []))
    results = []
    for call in calls:
        if call["name"] == ASK_USER:
            continue
        used += 1
        if used > MAX_TOOL_CALLS:
            content = "이번 턴 도구 호출 상한에 걸려 실행하지 않았어요."
        else:
            content, rule_ids = _run_one(state, config, call["name"], call["args"])
            cited.extend(i for i in rule_ids if i not in cited)
        results.append(ToolMessage(content=content, tool_call_id=call["id"]))
    asks = [c for c in calls if c["name"] == ASK_USER]
    if asks:
        ask = AskUserInput.model_validate(asks[0]["args"])
        emit(AskUserEvent(question_id=asks[0]["id"], text=ask.question, choices=ask.choices))
        # 두 번째 질문부터는 한 번에 하나만 묻도록 돌려보냅니다.
        results.extend(
            ToolMessage(content="한 번에 하나만 물어요.", tool_call_id=c["id"]) for c in asks[1:]
        )
    return {"messages": results, "tool_calls": used, "cited": cited}


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
