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
| router | 경로·반환 타입(응답 모델)·`responses`·`Depends`, 서비스 호출 | 업무 판단, DB 쿼리, 직접 commit |
| service | 업무 규칙, 트랜잭션 경계(`commit`), `AppError` 하위 예외 던지기 | `Request`·`HTTPException`·상태 코드 다루기 |
| repository | SQLAlchemy 조회·저장(`flush`까지) | commit, 업무 판단, 예외를 HTTP로 바꾸기 |
| schemas | 요청·응답 Pydantic(`XxxCreate/Read/Update`), 공통은 `schemas/common.py` | DB 모델 import |

- 역방향·건너뛰기 import 금지 (router가 repository를 직접 부르지 않음).
- DB 세션은 `app/core/db.py`의 `DbSession`, 설정은 `get_settings()`로 주입.
- 새 모델은 `app/models/__init__.py`에서 import → `uv run alembic revision --autogenerate -m "..."`.
- 새 라우터는 `app/api/routers/`에 두고 `app/main.py`에서 `include_router`.

## 응답·에러

- 성공은 감싸지 않음. 목록은 `Page[T]`.
- 응답 모델은 함수 반환 타입(`-> AccountRead`)으로 정하고 `response_model=`은 쓰지 않음. 반환 타입과 응답이 다를 때(`Response` 반환 등)만 예외.
- 실패는 `app/core/errors.py`의 예외만: `NotFoundError`, `ConflictError`, `BadRequestError`, `RateLimitedError`, `LlmUnavailableError`, 필요하면 `AppError` 상속. `HTTPException` 직접 사용 금지.
- 새 오류 코드는 `app/schemas/common.py`의 `ErrorCode`에만 추가.
- 라우터에 `responses=error_responses(...)`(`app/api/responses.py`)로 가능한 오류 상태를 적음.
- API를 바꾸면 루트에서 `pnpm gen:api`를 실행해 `frontend/src/types/api.gen.ts`를 같은 변경에 포함.

## 개인정보 (데모: 실제 개인정보를 받지 않음)

- 주민등록번호 필드는 만들지 않음.
- 이름·생년·성별·휴대폰·이메일·주소·은행·계좌는 `user_profiles` 테이블에만 둠. 값은 seed 가상 값만, 계좌는 `app/core/crypto.py`로 암호화하고 화면에는 끝 4자리만.
- `user_profiles` 값은 LLM 입력 모델·LangGraph State·트레이스·로그·예외 메시지에 넣지 않음. 서류 응답의 표시값(`profile_display`)으로만 내보냄.
- 로그에 요청 본문·사용자 입력·LLM 프롬프트/응답 원문을 남기지 않음. 남길 것은 code·경로·요청 ID·건수.
- 예외 `message`·`details`에 입력값을 넣지 않음.
- 음성 원본과 이력서 서류(`purpose=resume_doc`)는 판독 후 지움. 구직활동 증빙(`purpose=evidence`)만 `UPLOAD_DIR/{user_id}/`에 보관.

## 테스트

- 서비스·순수 로직 → `tests/unit/` (DB 없이, `fake_llm`).
- 라우터→DB 흐름 → `tests/integration/` (`pytestmark = pytest.mark.integration`, `client` 픽스처).
- 오류 경로(404·422 등)도 응답 형식까지 확인. 테스트 데이터는 합성 값만.
