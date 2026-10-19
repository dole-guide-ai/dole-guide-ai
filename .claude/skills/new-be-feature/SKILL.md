---
name: new-be-feature
description: 백엔드에 새 API 기능(테이블·엔드포인트)을 추가할 때 사용. model → 마이그레이션 → schema → repository → service → router → 테스트 → gen:api 순서로 이 레포 규칙대로 만든다.
---

# 백엔드 기능 추가

규칙: `.claude/rules/backend.md`, `docs/CONVENTIONS.md` 5·7절. 명령은 `backend/`에서 실행.

순서대로 진행하고, 단계마다 다음으로 넘어가기 전에 확인한다.

1. **model** — `app/models/<대상>.py`, 테이블명 snake_case 복수형. `app/models/__init__.py`에 import 추가.
   - 개인정보 필드(주민번호·전화·이메일·실명·주소) 금지.
2. **마이그레이션** — `uv run alembic revision --autogenerate -m "<무엇을>"` → 생성 파일을 열어 의도한 변경만 있는지 확인 → `uv run alembic upgrade head`.
3. **schema** — `app/schemas/<대상>.py`에 `XxxCreate`·`XxxRead`(`model_config = ConfigDict(from_attributes=True)`)·필요 시 `XxxUpdate`. 목록 응답은 `app/schemas/common.py`의 `Page[XxxRead]`.
4. **repository** — `app/repositories/<대상>_repository.py`. 조회·저장만, `flush`까지(commit 금지).
5. **service** — `app/services/<대상>_service.py`. 업무 규칙, `db.commit()`, 실패는 `app/core/errors.py`의 `NotFoundError` 등만 raise(메시지는 쉬운 한국어, 입력값 금지). 새 오류 종류가 필요하면 `ErrorCode`(`app/schemas/common.py`)에 추가 + `AppError` 상속.
6. **router** — `app/api/routers/<대상>.py`, 경로 kebab-case 복수형, `tags`, `response_model`, `responses=error_responses(...)`(`app/api/responses.py`). `DbSession` 주입 후 service만 호출. `app/main.py`에 `include_router`.
7. **테스트**
   - `tests/unit/test_<대상>_service.py`: service 로직 (가능하면 DB 없이)
   - `tests/integration/test_<대상>.py`: `pytestmark = pytest.mark.integration`, `client`로 성공 + 404/422 오류 형식 `{code, message, details}` 확인. 합성 데이터만.
8. **마무리** — 루트에서 `pnpm gen:api` → `uv run lint-imports` → `pnpm check:be`(integration은 `pnpm dev:db` 후).

견본: `app/api/routers/health.py`, `tests/unit/test_errors.py`.
