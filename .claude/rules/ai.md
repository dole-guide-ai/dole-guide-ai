---
paths:
  - "backend/app/agent/**"
  - "backend/evals/**"
  - "backend/app/schemas/forms/**"
---

# AI 작성 규칙

상세 표는 `docs/CONVENTIONS.md` 6절. 공용 부품 쓰는 법은 `backend/app/agent/README.md`.

| 위치 | 둘 것 |
| --- | --- |
| `agent/graph.py` | LangGraph 그래프 조립 |
| `agent/nodes/` | 노드 함수 (snake_case 동사형) |
| `agent/tools/` | 도구 (`동사_명사`) |
| `agent/prompts/` | 프롬프트 파일(`<영역>/<이름>.md`). 코드 문자열 금지, `load_prompt("<영역>/<이름>")`로 읽음 |
| `agent/responder.py` | 대화 턴 서비스 ↔ 그래프 연결. 노드는 `events.emit(...)`으로 화면 이벤트를 냄 |
| `agent/checkpointer.py` | Postgres 체크포인터(`thread_id`=user_id). 테이블은 Alembic 마이그레이션으로만 |
| `agent/tools/langchain.py` | 레지스트리 도구 → LangChain 도구(`as_langchain_tools`) |
| `agent/gateway/` | 모델 호출의 유일한 창구. 모델명은 설정(`.env`)에서만 |
| `agent/input/` | 음성·사진 입력 처리 |

- 흐름 제어는 LangGraph. LangChain은 부품(모델 래퍼, `@tool`, 텍스트 분할, 검색)으로만 쓰고 `AgentExecutor`·레거시 체인은 쓰지 않음.
- 그래프 호출은 서비스에서, 라우터는 SSE 스트리밍만. 이벤트 이름은 `shared/sse-events.json`.
- 에이전트 코드는 `gateway.get_chat_model()`처럼 모듈 경유로 호출(테스트의 `fake_llm`이 바꿔 끼움).
- LLM 호출 실패는 `LlmUnavailableError`, 한도 초과는 `RateLimitedError`로 던짐. 스트림 도중이면 `error` 이벤트.
- 관측(LangSmith)은 gateway 한 곳에서만 연결, 키가 없으면 꺼짐. 보내기 전 개인정보 마스킹.
- 쓰기 도구는 지금 질문이 다루는 칸만 쓸 수 있음. `status`·회차·절차 날짜·`user_profiles`는 도구로 쓰지 않음. 본인 답변 칸은 `record_user_answer`만.
- 그래프 상태(`AgentState`)는 체크포인트에 저장되므로 DB 세션·`user_profiles` 값을 넣지 않음. 턴 정보·`ToolContext`는 `config["configurable"]`로 받음.
- 사용자 입력·프롬프트·응답 원문을 로그에 남기지 않음.
- 모델·프롬프트·규칙표를 바꾸면 `pnpm test:eval` 결과를 PR에 첨부.

## 실제 모델로 확인·재현할 때 

- 재현 스크립트는 **개발 DB(`dole`)에 붙이지 않음.** `SessionLocal`을 직접 쓰면 개발 DB에 빈 평가 계정이 남아 `/personas`가 500으로 깨짐. 대신 `cd backend && uv run python -m scripts.dev.chat_turns "말1" "말2"`를 씀(테스트 DB `dole_test`에만 쓰고 끝나면 지움, error 이벤트와 원래 예외를 보여 줌).
- 평가 드라이버(`evals/golden/runner._enter`)는 DB 이름이 `_test`로 끝나지 않으면 멈춤. 이 검사를 우회하지 않음.
- 테스트 DB에 평가 계정(`eval_*`)이 남으면 `test_persona_cards`가 깨짐. 스크립트는 끝에서 자기 계정을 지우고, 중간에 끊겼으면 `delete from users where persona_id like 'eval_%';` 다음 `delete from personas where persona_id like 'eval_%';` 순서로 지움(users가 personas를 참조하고, 계정의 나머지 행은 users를 지우면 같이 지워짐).
- 화면에 "지금 답을 만들기 어려워요"만 보이면 턴 도중 예외가 `error` 이벤트로 바뀐 것. 원인은 서버 로그의 `turn failed code=… type=…` 또는 위 스크립트로 봄.
- 구조화 출력(`with_structured_output`)에 `Any`·자유 dict 필드가 있으면 OpenAI 기본(JSON 스키마 엄격) 방식이 거부함 → `method="function_calling"`을 명시. 스키마를 바꾸면 실제 모델로 한 턴 돌려 봄(가짜 모델 테스트는 이 오류를 못 잡음).
- 턴은 계정 행을 잠근 채(`try_lock_turn`) 모델을 기다리므로, 모델 호출이 멈추면 그 계정의 새 말·초기화가 모두 "답을 만드는 중"으로 막힘. 화면이 멈춘 듯 보이면 `select pid, state, now()-xact_start, left(query,60) from pg_stat_activity where datname='dole' and state='idle in transaction'`로 확인하고 `pg_terminate_backend(pid)`로 푼다. 모델 대기 시간(`LLM_TIMEOUT_SECONDS`)은 턴 타임아웃 안에 들어오게 둔다.
