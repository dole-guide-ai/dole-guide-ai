"""패널 서브그래프의 두 노드: agent(LLM)와 tools(도구 실행) (노션 「AI 설계」 2-1·2-2-1·2-4).

agent ⇄ tools를 AGENT_MAX_TOOL_ROUNDS바퀴까지 돕니다. 상한에 닿으면 오류로 끝내지 않고 마지막
도구 결과로 답을 정리합니다. 답 문장은 바로 흘려보내지 않고 verify가 검사한 뒤 내보냅니다(2-6).

- LLM에는 개인정보를 가린 글만 넘기고, 사용자 말 · 서류 글 · 도구 결과는 untrusted 태그로 감쌉니다.
- 도구 거절(권한 밖 칸, 서비스 409·422)은 예외로 끝내지 않고 사유를 LLM에게 돌려줍니다.
- 도구가 낸 칸 변경은 form_update로 바로 화면에 보냅니다.
"""

import json
from collections.abc import Callable
from typing import Any

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from pydantic import ValidationError

from app.agent import gateway, guard
from app.agent.events import emit
from app.agent.graph_config import tool_context_of
from app.agent.panels import Panel, prompt_name, tools_for
from app.agent.prompts import load_prompt
from app.agent.state import AgentState
from app.agent.tools.langchain import as_langchain_tools
from app.agent.tools.registry import ToolError, run_tool
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.common import FormUpdate
from app.schemas.messages import ToolCallEvent

# 답을 만드는 동안 보여 줄 진행 표시 이름 (2-6 F, 프론트 TOOL_LABEL)
COMPOSE_REPLY = "compose_reply"
SEARCH_GUIDE = "search_guide"
STARTED = "started"
FINISHED = "finished"


def system_prompt(panel: Panel) -> str:
    return load_prompt("common/system") + "\n\n" + load_prompt(prompt_name(panel))


def context_message(state: AgentState) -> str:
    """이번 질문과 단계. 질문 문구는 화면이 따로 보여 주므로 답에 다시 쓰지 않게 알립니다."""
    question = state.get("question") or {}
    lines = [f"지금 패널: {state.get('panel')}"]
    if question:
        lines.append(f"지금 질문 ID: {question.get('id')} (칸: {question.get('path') or '-'})")
        lines.append(f"화면이 보여 줄 질문: {question.get('text')}")
        if question.get("values"):
            lines.append(f"선택지 값: {json.dumps(question['values'], ensure_ascii=False)}")
    if state.get("doc_failed"):
        lines.append("올린 서류의 글자를 읽지 못했어요.")
    return "\n".join(lines)


def user_message(state: AgentState) -> HumanMessage:
    parts = [guard.untrusted("user", state.get("text", ""))]
    parts += [guard.untrusted("document", text) for text in state.get("attachments", [])]
    return HumanMessage("\n".join(parts))


def _history(state: AgentState) -> list[AnyMessage]:
    keep = get_settings().agent_history_messages
    return list(state.get("messages", []))[-keep:]


def _bind(panel: Panel, config: RunnableConfig) -> Any:
    model = gateway.get_chat_model("agent")
    ctx = tool_context_of(config)
    if ctx is None:
        return model
    try:
        return model.bind_tools(as_langchain_tools(ctx, tools_for(panel)))
    except NotImplementedError:  # 도구를 못 받는 모델(테스트 가짜 모델)
        return model


def text_of(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    return "".join(p.get("text", "") for p in content if isinstance(p, dict)).strip()


def make_agent(panel: Panel) -> Callable[[AgentState, RunnableConfig], dict[str, Any]]:
    def agent(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        scratch = list(state.get("scratch", []))
        if not scratch:
            emit(ToolCallEvent(name=COMPOSE_REPLY, status=STARTED))
        messages: list[BaseMessage] = [
            SystemMessage(system_prompt(panel)),
            SystemMessage(context_message(state)),
            *_history(state),
            user_message(state),
            *scratch,
        ]
        answer = _bind(panel, config).invoke(messages)
        if not isinstance(answer, AIMessage):
            answer = AIMessage(text_of(answer))
        scratch.append(answer)
        calls = answer.tool_calls
        if calls and state.get("rounds", 0) < get_settings().agent_max_tool_rounds:
            return {"scratch": scratch, "reply": None}
        # 상한에 닿았거나 도구를 부르지 않으면 답 문장. 비었으면 verify가 고정 답으로 바꿉니다.
        return {"scratch": scratch, "reply": text_of(answer)}

    agent.__name__ = f"{panel}_agent"
    return agent


def make_tools(panel: Panel) -> Callable[[AgentState, RunnableConfig], dict[str, Any]]:
    allowed = set(tools_for(panel))

    def tools(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        ctx = tool_context_of(config)
        scratch = list(state.get("scratch", []))
        facts = list(state.get("facts", []))
        sources = list(state.get("sources", []))
        answer = scratch[-1]
        not_found = state.get("guide_not_found", False)
        for call in getattr(answer, "tool_calls", []):
            name = call["name"]
            emit(ToolCallEvent(name=name, status=STARTED))
            try:
                if ctx is None or name not in allowed:
                    raise ToolError("이 단계에서 쓸 수 없는 도구예요.")
                result = run_tool(ctx, name, call.get("args") or {})
            except (ToolError, AppError) as exc:
                content = str(getattr(exc, "message", None) or exc)
            except ValidationError:
                content = "도구 인자가 맞지 않아요. 칸 경로와 값 모양을 확인해 주세요."
            else:
                for update in result.get("updates", []):
                    emit(FormUpdate.model_validate(update))
                if name == SEARCH_GUIDE and result.get("not_found"):
                    not_found = True
                if name == SEARCH_GUIDE:
                    # 자료 번호 [n]은 턴 안에서 이어 붙입니다(여러 번 검색해도 겹치지 않게).
                    for chunk in result.get("chunks", []):
                        chunk["ref"] = len(sources) + 1
                        sources.append(chunk)
                content = json.dumps(result, ensure_ascii=False, default=str)
                facts.append(content)
            emit(ToolCallEvent(name=name, status=FINISHED))
            scratch.append(
                ToolMessage(guard.untrusted("tool_result", content), tool_call_id=call["id"])
            )
        return {
            "scratch": scratch,
            "rounds": state.get("rounds", 0) + 1,
            "facts": facts,
            "sources": sources,
            "guide_not_found": not_found,
        }

    tools.__name__ = f"{panel}_tools"
    return tools


def after_agent(state: AgentState) -> str:
    """도구를 불렀으면 tools로, 답이 나왔으면 verify로."""
    return "verify" if state.get("reply") is not None else "tools"
