"""verify 노드: 답을 검사한 뒤에만 화면으로 흘려보냅니다 (노션 「AI 설계」 2-6 A+F, N-03).

검사 (LLM 없음)
- 숫자 · 날짜: 답에 나온 숫자가 도구 결과 · 검색 자료 · 사용자 말 · 질문에 그대로 있어야 합니다.
- 자료 번호 [n]: 이번 턴에 실제로 찾은 자료 번호만 씁니다.
- 출력 가드: 수급 · 인정 단정, 개인정보 (guard.check_output).

실패하면 한 번 다시 만들고, 또 실패하면 고정 답으로 바꿉니다(틀린 설명을 내보내지 않음).
통과한 답은 글자 조각(token)으로 내보내고, 근거 줄(done)은 쓴 자료로 만듭니다.
"""

import re
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.agent import gateway, guard, replies
from app.agent.events import emit
from app.agent.nodes.panel import COMPOSE_REPLY, FINISHED, system_prompt, text_of, user_message
from app.agent.panels import Panel
from app.agent.prompts import load_prompt
from app.agent.state import AgentState
from app.schemas.messages import CiteLink, DoneEvent, TokenEvent, ToolCallEvent

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
REF = re.compile(r"\s?\[(\d+)\]")
# 안내 문구에 늘 쓰는 번호 (고객상담센터, 고용24 개수 제한 등)
KNOWN_NUMBERS = frozenset({"1350", "24", "3"})
MAX_CITES = 3
CITE_SEPARATOR = " · "
CITE_JOIN = " / "


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER.findall(text)}


def problems(reply: str, state: AgentState) -> list[str]:
    """답의 문제 목록. 비어 있으면 통과입니다."""
    found: list[str] = []
    if not reply.strip():
        return ["답이 비었어요."]
    question = state.get("question") or {}
    known = " ".join(
        [
            state.get("text", ""),
            *state.get("attachments", []),
            *state.get("facts", []),
            *(c.get("text", "") for c in state.get("sources", [])),
            str(question.get("text", "")),
        ]
    )
    unknown = _numbers(REF.sub("", reply)) - _numbers(known) - KNOWN_NUMBERS
    if unknown:
        found.append("도구 결과에 없는 숫자: " + ", ".join(sorted(unknown)))
    refs = {int(n) for n in REF.findall(reply)}
    valid = {c.get("ref") for c in state.get("sources", [])}
    if refs - valid:
        found.append("찾지 않은 자료 번호를 썼어요.")
    verdict = guard.check_output(reply)
    if verdict.blocked:
        found.append("지키지 않은 규칙: " + ", ".join(verdict.labels))
    return found


def _regenerate(state: AgentState, issues: list[str]) -> str:
    panel = Panel(state["panel"])
    feedback = load_prompt("verify/regenerate").replace("{problems}", "\n".join(issues))
    messages = [
        SystemMessage(system_prompt(panel)),
        user_message(state),
        *state.get("scratch", []),
        HumanMessage(feedback),
    ]
    return text_of(gateway.get_chat_model("agent").invoke(messages))


def _fallback(state: AgentState) -> str:
    if state.get("sources"):
        return replies.reply("fallback_sources")
    return replies.reply("fallback")


def _cite(reply: str, state: AgentState) -> tuple[str, DoneEvent]:
    """답에서 자료 번호를 빼고, 쓴 자료로 근거 줄을 만듭니다(문서 단위, 최대 3개)."""
    used = {int(n) for n in REF.findall(reply)}
    text = REF.sub("", reply).strip()
    chunks = [c for c in state.get("sources", []) if c.get("ref") in used]
    if not chunks and reply == replies.reply("fallback_sources"):
        chunks = state.get("sources", [])
    links: dict[str, CiteLink] = {}
    refs: list[str] = []
    for chunk in chunks:
        key = chunk.get("source_id") or chunk.get("title", "")
        refs.append(key)
        links.setdefault(
            key,
            CiteLink(
                title=chunk.get("source_name", ""),
                url=chunk.get("url"),
                updated_on=chunk.get("updated_on"),
            ),
        )
    picked = list(links.values())[:MAX_CITES]
    cite = (
        CITE_JOIN.join(
            CITE_SEPARATOR.join(x for x in (link.title, link.updated_on) if x) for link in picked
        )
        or None
    )
    return text, DoneEvent(cite=cite, rule_refs=list(dict.fromkeys(refs)), cite_links=picked)


def _stream(text: str) -> None:
    for piece in re.split(r"(\s+)", text):
        if piece:
            emit(TokenEvent(text=piece))


def verify(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    notes = state.get("notes", [])
    reply = state.get("reply") or ""
    if state.get("guide_not_found") and not state.get("sources"):
        # 근거 자료를 찾지 못했으면 규칙 설명을 지어내지 않고 고정 답으로 (RAG 7.7)
        reply = replies.reply("not_found")
        emit(ToolCallEvent(name=COMPOSE_REPLY, status=FINISHED))
    elif not state.get("fixed"):
        issues = problems(reply, state)
        if issues:
            reply = _regenerate(state, issues)
            if problems(reply, state):
                reply = _fallback(state)
        emit(ToolCallEvent(name=COMPOSE_REPLY, status=FINISHED))
    text, done = _cite(reply, state)
    final = "\n".join([*notes, text]).strip()
    _stream(final)
    emit(done)
    return {
        "messages": [HumanMessage(state.get("text", "")), AIMessage(final)],
        "reply": final,
        "cite": [link.model_dump() for link in done.cite_links],
        "rule_refs": done.rule_refs,
        "scratch": [],
    }
