---
paths:
  - "backend/**"
---

# 백엔드 작성 규칙

상세 표는 `docs/CONVENTIONS.md` 5·7절.

## 계층 (한 방향만)

`app/api/routers` → `app/services` → `app/repositories` → `app/models`

| 계층 | 하는 일 | 하지 않는 일 |
| --- | --- | --- |
| router | 경로·`response_model`·`responses`·`Depends`, 서비스 호출 | 업무 판단, DB 쿼리, 직접 commit |
| service | 업무 규칙, 트랜잭션 경계(`commit`), `AppError` 하위 예외 던지기 | `Request`·`HTTPException`·상태 코드 다루기 |
| repository | SQLAlchemy 조회·저장(`flush`까지) | commit, 업무 판단, 예외를 HTTP로 바꾸기 |
| schemas | 요청·응답 Pydantic(`XxxCreate/Read/Update`), 공통은 `schemas/common.py` | DB 모델 import |

- 역방향·건너뛰기 import 금지 (router가 repository를 직접 부르지 않음).
- DB 세션은 `app/core/db.py`의 `DbSession`, 설정은 `get_settings()`로 주입.
- 새 모델은 `app/models/__init__.py`에서 import → `uv run alembic revision --autogenerate -m "..."`.
- 새 라우터는 `app/api/routers/`에 두고 `app/main.py`에서 `include_router`.

## 응답·에러

- 성공은 감싸지 않음. 목록은 `Page[T]`.
- 실패는 `app/core/errors.py`의 예외만: `NotFoundError`, `ConflictError`, `BadRequestError`, `RateLimitedError`, `LlmUnavailableError`, 필요하면 `AppError` 상속. `HTTPException` 직접 사용 금지.
- 새 오류 코드는 `app/schemas/common.py`의 `ErrorCode`에만 추가.
- 라우터에 `responses=error_responses(...)`(`app/api/responses.py`)로 가능한 오류 상태를 적음.
- API를 바꾸면 루트에서 `pnpm gen:api`를 실행해 `frontend/src/types/api.gen.ts`를 같은 변경에 포함.

## 개인정보 (데모: 실제 개인정보를 받지 않음)

- 스키마·모델에 주민등록번호·전화번호·이메일·실명·주소 필드를 만들지 않음.
- 로그에 요청 본문·사용자 입력·LLM 프롬프트/응답 원문을 남기지 않음. 남길 것은 code·경로·요청 ID·건수.
- 예외 `message`·`details`에 입력값을 넣지 않음.
- 음성·사진 원본은 처리 후 저장하지 않음.

## 테스트

- 서비스·순수 로직 → `tests/unit/` (DB 없이, `fake_llm`).
- 라우터→DB 흐름 → `tests/integration/` (`pytestmark = pytest.mark.integration`, `client` 픽스처).
- 오류 경로(404·422 등)도 응답 형식까지 확인. 테스트 데이터는 합성 값만.
