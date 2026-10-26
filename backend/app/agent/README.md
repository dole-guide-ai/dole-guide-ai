# app/agent

대화 턴 AI입니다. 설계 기준은 노션 「AI 설계: LangGraph 대화 턴 · RAG · 보안 · 평가」와 하위 「RAG 기반 하이브리드 검색 시스템 기술 설계 (복사본)」입니다. 규칙은 `.claude/rules/ai.md`를 따릅니다.

## 한 턴의 흐름

```
POST /accounts/{id}/messages
  → services/chat.py      턴 잠금 · 말풍선 저장 · 타임아웃 · 오류 → error 이벤트 · 턴 끝 commit
  → responder.get_responder()(TurnInput)
  → graph.build_graph(checkpointer).stream({}, config, stream_mode="custom")
  → 노드에서 events.emit(...) → SSE: tool_call → form_update → token → done → ask_user
```

## 그래프 (`graph.py`)

바깥 그래프 하나 + 패널 서브그래프 넷.

```
START → preprocess → load_context ─(고정 경로)──────────────────────────────┐
                          └─(패널 라우터)→ {panel}_agent ⇄ {panel}_tools ──→ verify → ask → END
```

| 노드 | 파일 | 하는 일 |
|---|---|---|
| preprocess | `nodes/preprocess.py` | 개인정보 가림(`input/pii.py`), 서류 로컬 판독(`input/documents.py`), 입력 가드(`guard/`) |
| load_context | `nodes/context.py` | 절차 단계 · 직전 질문으로 패널 선택(LLM 아님), 다음 질문 · 쓸 수 있는 칸, 고정 경로 |
| `{panel}_agent` · `{panel}_tools` | `nodes/panel.py`, `panels.py` | 패널 프롬프트 + 패널 도구로 값 추출 → 도구 → 답 문장. 최대 `AGENT_MAX_TOOL_ROUNDS`바퀴 |
| verify | `nodes/verify.py` | 숫자 · 자료 번호 · 출력 가드를 검사한 뒤에만 답을 흘려보냄. 틀리면 한 번 다시, 또 틀리면 고정 답 |
| ask | `nodes/ask.py` | 다음 질문(ask_user). 문구는 `data/templates/questions.json` |

패널(서브그래프) = 오른쪽 패널 하나: `resume`(A 이력서) · `round`(B 회차 활동) · `application`(C 신청서 본인 답변) · `education`(교육 · 프로그램 조회). `search_guide`(RAG)는 모든 패널의 공용 도구입니다.

고정 경로(LLM 0회): "전체 순서가 궁금해요", 인사 · 잡담(`data/templates/replies.json`), 지금 단계가 아닌 서류 고치기 안내, 신청서 선택지 그대로의 답, 이력서 확인 질문의 "네, 맞아요".

### 지킬 약속

- 무엇을 물을지는 규칙 함수(`app/rules`: `next_resume_question`, `next_application_question`)가, 쓸 수 있는 칸은 `ToolContext.allowed_paths`가 정합니다. LLM은 값 추출과 답 문장만 만듭니다.
- 회차 · 건수 · 날짜 · 금액은 도구 결과만 씁니다(verify가 대조).
- 사용자 원문은 그래프 입력으로 넘기지 않습니다. preprocess가 가린 글만 상태(`state.py`)에 남깁니다. `user_profiles`는 읽지 않습니다.
- 사용자 글 · 서류 글 · 도구 결과 · 검색 자료는 `guard.untrusted(...)`로 감싸 지시가 아닌 데이터로 넘깁니다.
- 도구가 부른 서비스의 commit은 저장점 확정으로 바뀌고(`core/db.deferred_commit`), 실제 commit은 턴 끝에 한 번입니다. 턴 잠금이 도중에 풀리지 않습니다.
- 그래프는 질문 뒤에 멈추지(interrupt) 않습니다. 직전 질문은 체크포인트의 `question`에 남고, 다음 메시지는 새 턴으로 시작합니다.

## 부품

| 부품 | 위치 | 쓰는 법 |
|---|---|---|
| 모델 호출 | `gateway` | `gateway.get_chat_model("agent" · "extract" · "judge")`, `get_embeddings()`, `get_guard_model()`. 모델명은 `.env`에만. 테스트는 `fake_llm`(글만) · `scripted_llm`(도구 호출까지) 픽스처 |
| 트레이스 | `gateway.trace_config()` · `trace_callbacks()` | 요청 ID 연결, LangSmith로 보내기 전 개인정보 가림 |
| 화면 이벤트 | `events.emit` | 노드 안에서 `emit(TokenEvent(...))` 등. `done` · `ask_user`는 응답기가 체크포인트 저장 뒤 보냄 |
| 턴 정보 · 도구 문맥 | `graph_config.turn_of(config)` · `tool_context_of(config)` | 노드 시그니처는 `(state, config)` |
| 도구 | `tools/registry.py`, `tools/langchain.py` | `TOOLS_BY_PANEL`, `run_tool(ctx, name, args)`, `as_langchain_tools(ctx, names)` |
| 질문 · 고정 답 | `questions.py`, `replies.py` | 템플릿은 `data/templates/` |
| 가드 | `guard/` | `check_input` · `check_output` · `untrusted`. 백엔드는 `GUARD_BACKENDS`(rules 기본, prompt_guard · llama_guard 선택). 패턴은 `data/guard/patterns.json` |
| 서류 판독 | `input/documents.py` | 이미지 RapidOCR, pdf · docx · hwpx · hwp 파서. 원본은 외부 모델로 보내지 않음 |
| RAG | `services/knowledge.py`, 도구 `search_guide` | Kiwi + BM25S + pgvector + RRF(+리랭커 설정). 자료는 `scripts/ingest/load_chunks.py`로 적재 |
| 체크포인터 | `checkpointer.get_checkpointer()` | Postgres, `thread_id`=user_id. 테스트는 `InMemorySaver()` |
| 프롬프트 | `prompts/<영역>/<이름>.md` | `common/system`, `<panel>/agent`, `verify/regenerate` |
| 평가 | `backend/evals/` | 골든셋 · RAG · 보안 · 일상 질문. `evals/README.md` |

## 설정

`AGENT_MAX_TOOL_ROUNDS` · `AGENT_HISTORY_MESSAGES`, `RAG_*` · `RERANKER_*`, `GUARD_*` · `PROMPT_GUARD_MODEL` · `GUARD_LLM_*`, `WORK24_TRAINING_API_KEY` · `WORK24_PROGRAM_API_KEY`(공통코드 키 `WORK24_CODE_API_KEY`는 수집 스크립트만). 선택 의존성: `uv sync --extra guard`(Prompt Guard 2), `--extra rerank`(리랭커), `--extra rageval`(RAGAS · AutoRAG 내보내기).

## 테스트

- 순수 규칙: `tests/unit/test_agent_rules.py`, `test_knowledge_search.py`, `test_rag_metrics.py`
- 한 턴: `tests/integration/test_agent_graph.py`(라우터 · 고정 경로 · 도구 · verify · 가드 · 저장점), `test_knowledge.py`(검색 · 근거 줄)
- 공용 부품: `tests/unit/test_agent_skeleton.py`
