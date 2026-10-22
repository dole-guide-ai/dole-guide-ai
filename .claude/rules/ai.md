---
paths:
  - "backend/app/agent/**"
  - "backend/evals/**"
  - "backend/app/schemas/forms/**"
---

# AI 작성 규칙

상세 표는 `docs/CONVENTIONS.md` 6절.

| 위치 | 둘 것 |
| --- | --- |
| `agent/graph.py` | LangGraph 그래프 조립 |
| `agent/nodes/` | 노드 함수 (snake_case 동사형) |
| `agent/tools/` | 도구 (`동사_명사`) |
| `agent/prompts/` | 프롬프트 파일. 코드 문자열 금지 |
| `agent/gateway/` | 모델 호출의 유일한 창구. 모델명은 설정(`.env`)에서만 |
| `agent/input/` | 음성·사진 입력 처리 |

- 흐름 제어는 LangGraph. LangChain은 부품(모델 래퍼, `@tool`, 텍스트 분할, 검색)으로만 쓰고 `AgentExecutor`·레거시 체인은 쓰지 않음.
- 그래프 호출은 서비스에서, 라우터는 SSE 스트리밍만. 이벤트 이름은 `shared/sse-events.json`.
- 에이전트 코드는 `gateway.get_chat_model()`처럼 모듈 경유로 호출(테스트의 `fake_llm`이 바꿔 끼움).
- LLM 호출 실패는 `LlmUnavailableError`, 한도 초과는 `RateLimitedError`로 던짐. 스트림 도중이면 `error` 이벤트.
- 관측(LangSmith)은 gateway 한 곳에서만 연결, 키가 없으면 꺼짐. 보내기 전 개인정보 마스킹.
- 쓰기 도구는 지금 질문이 다루는 칸만 쓸 수 있음. `status`·회차·절차 날짜·`user_profiles`는 도구로 쓰지 않음. 본인 답변 칸은 `record_user_answer`만.
- 사용자 입력·프롬프트·응답 원문을 로그에 남기지 않음.
- 모델·프롬프트·규칙표를 바꾸면 `pnpm test:eval` 결과를 PR에 첨부.
