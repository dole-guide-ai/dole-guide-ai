"""preprocess 노드: 사용자 글을 가리고, 서류를 읽고, 입력 가드를 거칩니다.

노션 「AI 설계」 2-1·4·5절.

- 개인정보(주민번호·카드·계좌·전화·이메일)는 모델에 넘기기 전에 토큰으로 바꿉니다.
- 올린 서류는 로컬에서 글을 뽑고(input/documents.py) 같은 가림·가드를 거칩니다.
- 지시 주입으로 판정되면 LLM을 부르지 않고 고정 답으로 끝냅니다.
"""

from typing import Any

from langchain_core.runnables import RunnableConfig

from app.agent import guard, replies
from app.agent.graph_config import tool_context_of, turn_of
from app.agent.input import documents, pii
from app.agent.state import AgentState


def preprocess(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    turn = turn_of(config)
    text, findings = pii.mask(turn.text)
    notes: list[str] = []
    if findings:
        notes.append(replies.reply("pii_masked"))

    attachments: list[str] = []
    doc_failed = False
    ctx = tool_context_of(config)
    if turn.file_ids and ctx is not None:
        read = documents.read_files(ctx.db, ctx.account, turn.file_ids)
        doc_failed = read.failed
        for raw in read.texts:
            masked, found = pii.mask(raw)
            attachments.append(masked)
            if found and not notes:
                notes.append(replies.reply("pii_masked"))

    verdicts = [guard.check_input(text), *(guard.check_input(a) for a in attachments)]
    blocked = any(v.blocked for v in verdicts)
    return {
        "text": text,
        "attachments": [] if blocked else attachments,
        "doc_failed": doc_failed,
        "blocked": blocked,
        "notes": notes,
        "scratch": [],
        "rounds": 0,
        "facts": [],
        "sources": [],
        "reply": replies.reply("blocked") if blocked else None,
        "fixed": blocked,
        "cite": [],
        "rule_refs": [],
    }
