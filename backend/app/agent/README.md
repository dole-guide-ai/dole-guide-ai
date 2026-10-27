# app/agent

AI 엔지니어링을 시작할 때 공통으로 쓰는 부품입니다. 노드 구성, 상태 모양, 프롬프트 내용은 정하지 않았습니다. 영역을 맡은 사람이 설계합니다. 규칙은 `.claude/rules/ai.md`를 따릅니다.

## 한 턴의 흐름

```
POST /accounts/{id}/messages
  → services/chat.py      턴 잠금 · 말풍선 저장 · 타임아웃 · 오류 → error 이벤트
  → responder.get_responder()(TurnInput)
  → graph.build_graph(checkpointer).stream(..., stream_mode="custom")
  → 노드에서 events.emit(...) → SSE(token · tool_call · ask_user · form_update · done · error)
```

그래프 노드와 분기는 `docs/agent/graph.md`(LangGraph가 뽑은 Mermaid)에 있습니다.
이력서 패널은 도구 루프가 아니라 읽기(값만 구조화 출력) → 코드 저장 → 말하기(확인 문장 + 질문 한 줄)로
갑니다(`nodes/resume.py`). 모델에게 "저장할지·물을지"를 맡기지 않고 "무엇인지"만 맡깁니다.

## 부품

| 부품 | 위치 | 쓰는 법 |
|---|---|---|
| 모델 호출 | `gateway` | `gateway.get_chat_model("agent")`. 모델명은 `.env`에만 둡니다. 테스트는 `fake_llm` 픽스처를 씁니다. |
| 화면 이벤트 | `events.emit` | 노드 안에서 `emit(TokenEvent(text=...))`, 마지막에 `emit(DoneEvent(...))`를 냅니다. |
| 턴 정보·도구 문맥 | `graph.turn_of(config)`, `graph.tool_context_of(config)` | 노드 시그니처를 `(state, config: RunnableConfig)`로 둡니다. 상태에 넣지 않으므로 체크포인트에 DB 세션이 남지 않습니다. |
| 도구 | `tools/registry.py`, `tools/langchain.py` | `as_langchain_tools(ctx, TOOLS_BY_PANEL["round"])` → `model.bind_tools(...)`·`ToolNode(...)`. `user_id`·`today`는 LLM 인자가 아닙니다. 칸 제한은 `ToolContext.allowed_paths`로 겁니다. |
| 체크포인터 | `checkpointer.get_checkpointer()` | Postgres. `thread_id`는 계정(user_id)이고, 테이블은 Alembic 0004가 만듭니다. 테스트는 `InMemorySaver()`를 씁니다. |
| 프롬프트 | `prompts/` | `prompts/<영역>/<이름>.md` 파일을 만들고 `load_prompt("<영역>/<이름>")`로 읽습니다. |
| 개인정보 | `input/pii.py` | `detect` · `mask` · `has_blocking`. 모델에 넘기기 전에 거칩니다. |
| 트레이스 | `gateway.trace_config()` | 응답기가 실행 config에 넣습니다(요청 ID). |
| 평가 | `backend/evals/` | `pnpm test:eval`. 모델·프롬프트·규칙표를 바꾸는 PR에는 결과를 첨부합니다. |

## 그래프 바꾸기

- `graph.py`의 `respond`는 예시 노드입니다. 노드는 `nodes/<영역>.py`에 두고 `build_graph`에서 잇습니다.
- `AgentState`에 필드를 더할 수 있습니다. 체크포인트에 저장되니 JSON으로 바꿀 수 있는 값만, 개인정보 컬럼(user_profiles)은 넣지 않습니다.
- 그래프 없이 테스트할 때는 `graph_responder(turn, InMemorySaver())`나 `run_tool(ctx, name, args)`를 씁니다(`tests/unit/test_agent_skeleton.py`).
- 금액·회차·건수·마감 판단은 규칙 함수(`app/rules`)와 도구가 합니다. LLM이 계산하지 않습니다.
