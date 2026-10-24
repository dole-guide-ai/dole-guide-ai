# AGENTS.md

AI 코딩 에이전트(Claude Code, Codex, Cursor 등)용 작업 안내입니다. 상세 규칙은 `docs/CONVENTIONS.md`가 기준입니다.

## 프로젝트

중장년층 실업급여 행정 도우미. 대화·음성·사진으로 고용24 이력서와 실업인정 신청서를 양식 그대로 완성합니다.

- `frontend/`: Next.js 16(App Router) · React 19.2 · TypeScript · Tailwind · TanStack Query · pnpm → Vercel 배포
- `backend/`: Python 3.14 · FastAPI · SQLAlchemy 2.0 · Alembic · LangGraph · uv → AWS Lightsail Docker Compose 배포
- `shared/sse-events.json`: 프론트·백엔드 공통 SSE 이벤트 이름

## 명령

```bash
# 루트
pnpm bootstrap               # 처음 한 번: 의존성·.env 생성·DB·마이그레이션 (pnpm setup은 pnpm 내장 명령이라 쓰지 않음)
pnpm dev:db | pnpm dev:be | pnpm dev:fe
pnpm test | pnpm check | pnpm test:eval | pnpm check:pr-size
pnpm gen:api                 # 백엔드 OpenAPI → frontend/src/types/api.gen.ts
docker compose up -d db      # Postgres + pgvector

# frontend/
pnpm dev | pnpm lint | pnpm format | pnpm typecheck | pnpm build

# backend/
uv run uvicorn app.main:app --reload
uv run ruff check --fix . && uv run ruff format .
uv run pytest
uv run alembic revision --autogenerate -m "메시지"
uv run alembic upgrade head   # pull해서 마이그레이션이 늘었으면 먼저 실행 (예: 0004 체크포인트 테이블이 없으면 대화가 실패)
```

팀원이 macOS와 Windows에서 개발합니다. 스크립트·훅·경로는 두 환경에서 모두 동작해야 합니다.

- npm script·lefthook 명령에 셸 전용 문법(`$()`, 파이프, `rm`, `cp`, `export`)을 쓰지 않습니다. 필요하면 `scripts/*.mjs`(Node)나 Python으로 작성합니다.
- 파일을 읽고 쓸 때 인코딩을 `utf-8`로 명시합니다. (Windows 기본 인코딩은 cp949)
- 경로는 `pathlib`/`node:path`로 다루고 `/`·`\\`를 직접 이어 붙이지 않습니다.
- 줄바꿈은 LF입니다(`.gitattributes`).
- 도구 버전(Node·pnpm·Python·uv)은 `mise.toml`이 기준입니다. 버전을 바꾸면 mise를 쓰지 않는 곳도 같이 맞춥니다: node·pnpm → `frontend/package.json`의 `engines`·`packageManager`(Vercel), python → `backend/pyproject.toml`의 `requires-python`·`backend/Dockerfile` 베이스 이미지, uv → `backend/Dockerfile`의 uv 이미지 태그.

작업을 마치기 전에 바꾼 영역의 린트·타입검사·테스트를 실행해 통과를 확인하세요.

## 반드시 지킬 것

- 패키지 관리자는 프론트 pnpm, 백엔드 uv만 씁니다. npm·pip·poetry를 쓰지 마세요.
- `frontend/src/types/api.gen.ts`는 직접 수정하지 않습니다. 백엔드 API를 바꾸면 `pnpm gen:api`를 실행해 같은 변경에 포함하세요.
- 백엔드 호출 방향은 라우터 → 서비스 → 레포지토리 한 방향입니다. 라우터에는 HTTP 처리만 둡니다.
- 실패 응답은 `{code, message, details}` 한 형식입니다. 백엔드는 `app/core/errors.py`의 `AppError` 하위 예외만 던지고(`HTTPException` 금지), 프론트는 `lib/api.ts`의 `ApiError`로 받습니다. 성공 응답은 감싸지 않습니다. (`docs/CONVENTIONS.md` 7절)
- 영역별 상세 규칙은 `.claude/rules/`(backend·frontend·ai)에 있습니다. 다른 에이전트도 해당 영역 작업 전에 읽으세요.
- DB 스키마 변경은 Alembic 마이그레이션으로만 합니다. 새 모델은 `app/models/__init__.py`에서 import해야 autogenerate가 인식합니다.
- 프롬프트는 코드 문자열이 아니라 `backend/app/agent/prompts/`의 파일로 둡니다.
- 모델명은 코드에 쓰지 않고 `app/core/config.py` 설정(.env)에서만 지정하고, LLM 호출은 `app/agent/gateway`를 거칩니다.
- `backend/experiments/` 코드를 서비스 코드에서 import하지 않습니다.
- 로그·테스트 데이터에 실제 개인정보(이름, 연락처, 주민등록번호, 발화 원문)를 넣지 않습니다. 합성 데이터만 씁니다.
- 비밀값을 저장소에 커밋하지 않습니다. `.env.example`에는 키 이름만 둡니다.
- 업무 로직·모델 호출은 FastAPI에 둡니다.

## 코드 스타일 요약

- 프론트: 컴포넌트 파일 PascalCase, 훅·유틸 camelCase, 라우트 폴더 kebab-case. 라우트 파일 외 컴포넌트는 `export const` 화살표 함수, 한 파일 한 컴포넌트, Props는 `{Component}Props` interface. `@/` 절대 경로. 쿼리 키는 `lib/queryKeys.ts`, SSE 이름은 `shared/sse-events.json`(`lib/sseEvents.ts`).
- 공통(프론트·백엔드): 숫자·식별 문자열은 이름 붙인 상수나 enum으로 한 곳에 두고, 두 곳 이상 반복되는 로직은 순수 함수·공용 훅으로 뺍니다. 위치는 `.claude/rules/frontend.md`·`backend.md`의 "상수·반복 코드" 절.
- Tailwind CSS v4(현재 4.3) 문법으로만 작성합니다.
  - `tailwind.config.js`를 만들지 않습니다. 테마는 `src/app/globals.css`의 `@theme`에 CSS 변수로 정의합니다.
  - v3 지시어(`@tailwind base` 등) 금지, `@apply`는 최소화합니다.
  - 바뀐 이름: `shadow-xs`·`shadow-sm`, `rounded-xs`·`rounded-sm`, `blur-xs`, `outline-hidden`, `ring-3`(기본 `ring`은 1px), `bg-linear-to-r`
  - CSS 변수: `bg-(--color-brand)` ✓ / `bg-[var(--color-brand)]` ✗. important: `flex!` ✓ / `!flex` ✗
  - 문법이 확실하지 않으면 context7으로 Tailwind v4 문서를 확인합니다.
- 백엔드: snake_case 모듈·함수, PascalCase 클래스, 테이블은 snake_case 복수형, API 경로는 kebab-case 복수형, Pydantic 모델은 `Read`/`Create`/`Update` 접미사.
- AI: 도구 이름은 `동사_명사`, 그래프 노드는 snake_case 동사형, 양식 스키마는 `app/schemas/forms/`에 양식당 한 파일, 규칙표 행마다 출처 URL·출처 날짜·검수자·검수일.

## AI 엔지니어링

LangGraph 에이전트 작업 전에 읽을 것:

- `backend/app/agent/README.md`: 공용 부품(gateway·`events.emit`·도구 어댑터·체크포인터·`load_prompt`·`pii`)과 한 턴의 흐름
- `.claude/rules/ai.md`: 위치·도구·개인정보 규칙 (Claude Code가 아니어도 읽습니다)
- 금액·회차·건수·마감 같은 판단은 `app/rules`의 규칙 함수와 도구가 합니다. LLM이 계산하지 않습니다.

### 영역 분담

<!-- TODO(팀 합의): 담당자별 영역과 공용 파일 변경 절차를 채웁니다. -->

| 영역 | 담당 | 노드 | 프롬프트 | 평가 시나리오 |
| --- | --- | --- | --- | --- |
| (미정) | | `agent/nodes/<영역>.py` | `agent/prompts/<영역>/` | `evals/scenarios/<영역>/` |

공용 파일(`agent/graph.py`, `AgentState`, `agent/responder.py`, `agent/tools/registry.py`)을 바꾸는 절차: (미정)

### 평가 기준

<!-- TODO(팀 합의): AI PR이 통과해야 할 지표와 기준값을 채웁니다. -->

| 골든셋 | 지표 | 기준 |
| --- | --- | --- |
| form_fill · grounding · masking · procedure | (미정) | (미정) |

## 배포

- 운영 구성은 `docker-compose.yml` 위에 `docker-compose.prod.yml`을 덮어써서 띄웁니다. 운영에서 DB(5432)·앱(8000) 포트를 외부에 열지 않습니다(외부는 Caddy 80·443만).
- 운영 값은 서버의 `/opt/dole-guide-ai/.env`에만 있습니다(템플릿 `deploy/.env.example`). 새 설정을 추가하면 `deploy/.env.example`과 `docker-compose.prod.yml`의 `backend.environment`에도 같이 추가합니다.
- 배포는 `deploy-server` 워크플로(SSH)로만 합니다. self-hosted runner는 쓰지 않습니다(public 레포).
- 컨테이너는 root가 아닌 사용자로 실행합니다(`backend/Dockerfile`).

## Git

- 브랜치: `feat|fix|hotfix/#이슈번호-내용`, develop에서 분기해 develop으로 PR (hotfix만 main).
- 커밋·PR 제목: `type(scope): 무엇을 왜` — type `feat|fix|refactor|style|design|docs|test|chore|ci`, scope `fe|be|ai|infra|docs`. 호환성 깨짐은 `type(scope)!:`.
- main·develop에 직접 push하지 않습니다. 한 PR은 한 영역, +1000줄 이내.
- PR을 만들면 PR을 올린 사람(지금 인증된 GitHub 계정)을 담당자(assignee)로 지정합니다. 팀원 이름을 고정해 쓰지 않습니다.
  - gh: `gh pr create --assignee @me`
  - GitHub MCP·API: `GET /user`로 로그인 이름을 얻어 `POST /repos/{owner}/{repo}/issues/{PR번호}/assignees`로 지정합니다.
  - 담당자가 빈 채로 만든 PR을 발견하면 같은 방법으로 채웁니다.

## 테스트

| 명령 (루트) | 내용 |
| --- | --- |
| `pnpm test` | FE 단위 + BE unit·integration |
| `pnpm check` | PR 전 전체 검사 (린트·포맷·타입·테스트) |
| `pnpm test:eval` | AI 평가 세트 (`backend/evals`, 기본 실행에서 제외) |

- FE: Vitest + Testing Library. 테스트 파일은 대상 옆에 `*.test.tsx`. API는 `src/test/mockFetch.ts`로 fetch를 대체하고, 렌더는 `src/test/renderWithProviders.tsx`를 씁니다.
- BE: `tests/unit/`(DB 없음), `tests/integration/`(`pytestmark = pytest.mark.integration`, DB 필요). 공용 픽스처는 `backend/conftest.py`:
  - `client`: 테스트 DB(`dole_test`, 자동 생성·마이그레이션)를 쓰는 TestClient. 테스트마다 롤백됩니다.
  - `db_session`: 레포지토리 테스트용 세션
  - `fake_llm(["응답", ...])`: 실제 모델 호출 없이 LLM 응답을 고정합니다. 에이전트 코드는 `gateway.get_chat_model()`처럼 모듈 경유로 호출하세요.
- 그래프는 DB 없이 `graph_responder(turn, InMemorySaver())`로 한 턴을 돌려 이벤트를 확인하고, 도구는 `run_tool(ctx, name, args)`로 그래프 없이 부릅니다(`tests/unit/test_agent_skeleton.py`).
- 평가: `backend/evals/README.md` 참고. 모델·프롬프트·규칙표 변경 PR에 결과를 첨부합니다.
- integration 테스트 전에 `pnpm dev:db`로 DB를 띄웁니다. DB가 없으면 integration 테스트는 skip됩니다.

## 에이전트 도구 (Claude Code)

- 플러그인: `.claude/settings.json`의 `enabledPlugins`. 레포를 열면 설치 안내가 뜹니다. (vercel, playwright, context7, pyright-lsp, typescript-lsp, deepeval, security-guidance, aws-core, pr-review-toolkit, github)
- LSP 플러그인은 언어 서버가 필요합니다. mise로 전역 설치합니다: `mise use -g npm:pyright npm:typescript-language-server npm:typescript`
- 자주 쓰는 검사 명령(`pnpm test`, `uv run pytest` 등)은 `permissions.allow`에 등록돼 승인 없이 실행됩니다.
- 읽기 차단(`permissions.deny`): 실제 `.env`·`.env.local`, `node_modules`, `.next`, `.venv`, `coverage`, 캐시, lock 파일, `openapi.json`. `.env.example`은 읽을 수 있습니다.
- 편집 후 훅(`.claude/hooks/after-edit.mjs`): 파일을 수정하면 그 파일만 ESLint·Prettier 또는 ruff로 정리하고, 관련 단위 테스트만 실행합니다(FE `vitest related`, BE 같은 이름의 `tests/unit/**/test_<파일명>.py`). 실패하면 결과가 바로 돌아오니 그 자리에서 고칩니다.
- vercel 플러그인의 React 베스트 프랙티스 스킬을 참고합니다. 브라우저는 같은 사이트의 Next BFF(`frontend/src/app/api/[...path]`)만 부르고 백엔드 주소를 모릅니다(`.claude/rules/frontend.md`).
- `.claude/launch.json`: 프론트(3000)·백엔드(8000) 실행 설정.
