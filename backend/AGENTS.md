# backend/AGENTS.md

공통 규칙은 루트 `AGENTS.md`를 따릅니다. 명령은 이 폴더(`backend/`)에서 실행합니다.

```bash
uv run uvicorn app.main:app --reload
uv run ruff check --fix . && uv run ruff format .
uv run pytest
```

## 기능 하나 붙이는 순서

설계는 노션 「API · ERD 설계」, 할 일은 「요구사항 목록」의 행(F-xx·N-xx)이 기준입니다.

1. 요청·응답 스키마는 `app/schemas/`에 이미 있습니다(설계 3.11). 바꿔야 하면 여기부터 고칩니다.
2. 라우터(`app/api/routers/`)의 `NotImplementedYetError`(501)를 지우고, 서비스(`app/services/`) → 레포지토리(`app/repositories/`)를 구현합니다.
3. 계산은 `app/rules/`의 순수 함수로 둡니다. 오늘 날짜는 인자로 받고, 라우터는 `Today` 의존성(`app/core/clock.py`)을 씁니다.
4. 계정 데이터는 `CurrentAccount`(`app/api/deps.py`)의 `user_id`로만 조회합니다.
5. 오류는 `app/core/errors.py` 예외 + `ErrorCode`(예: `ConflictError(code=ErrorCode.ROUND_CLOSED)`).
6. 테스트: 규칙·서비스는 `tests/unit/`, 라우터→DB는 `tests/integration/`(날짜는 `app.dependency_overrides[get_today]`로 고정).
7. 루트에서 `pnpm gen:api` → 프론트에서 해당 mock(`src/mocks/handlers.ts`)과 손으로 쓴 타입을 지우고 `api.gen.ts` 타입으로 바꿉니다.

시연 계정 seed는 `data/seeds/personas.json`(날짜는 입장일 기준 상대값)이고, 서버가 시작할 때 `personas` 테이블에 적재합니다.
