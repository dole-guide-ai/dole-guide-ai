# AGENTS.md

AI 코딩 에이전트(Claude Code, Codex, Cursor 등)용 작업 안내입니다. 상세 규칙은 `docs/CONVENTIONS.md`가 기준입니다.

## 프로젝트

중장년층 실업급여 행정 도우미. 대화·음성·사진으로 고용24 이력서와 실업인정 신청서를 양식 그대로 완성합니다.

- `frontend/`: Next.js(App Router) · TypeScript · Tailwind · TanStack Query · pnpm → Vercel 배포
- `backend/`: FastAPI · SQLAlchemy 2.0 · Alembic · LangGraph · uv → EC2 Docker Compose 배포
- `shared/sse-events.json`: 프론트·백엔드 공통 SSE 이벤트 이름

## 명령

```bash
# 루트
pnpm install                 # lefthook 훅 설치
pnpm gen:api                 # 백엔드 OpenAPI → frontend/src/types/api.gen.ts
docker compose up -d db      # Postgres + pgvector

# frontend/
pnpm dev | pnpm lint | pnpm format | pnpm typecheck | pnpm build

# backend/
uv run uvicorn app.main:app --reload
uv run ruff check --fix . && uv run ruff format .
uv run pytest
uv run alembic revision --autogenerate -m "메시지"
uv run alembic upgrade head
```

작업을 마치기 전에 바꾼 영역의 린트·타입검사·테스트를 실행해 통과를 확인하세요.

## 반드시 지킬 것

- 패키지 관리자는 프론트 pnpm, 백엔드 uv만 씁니다. npm·pip·poetry를 쓰지 마세요.
- `frontend/src/types/api.gen.ts`는 직접 수정하지 않습니다. 백엔드 API를 바꾸면 `pnpm gen:api`를 실행해 같은 변경에 포함하세요.
- 백엔드 호출 방향은 라우터 → 서비스 → 레포지토리 한 방향입니다. 라우터에는 HTTP 처리만 둡니다.
- DB 스키마 변경은 Alembic 마이그레이션으로만 합니다.
- 프롬프트는 코드 문자열이 아니라 `backend/app/agent/prompts/`의 파일로 둡니다.
- 모델명은 코드에 쓰지 않고 `app/core/config.py` 설정(.env)에서만 지정하고, LLM 호출은 `app/agent/gateway`를 거칩니다.
- `backend/experiments/` 코드를 서비스 코드에서 import하지 않습니다.
- 로그·테스트 데이터에 실제 개인정보(이름, 연락처, 주민등록번호, 발화 원문)를 넣지 않습니다. 합성 데이터만 씁니다.
- 비밀값을 저장소에 커밋하지 않습니다. `.env.example`에는 키 이름만 둡니다.
- 프론트는 서버 렌더링·Next.js 캐시를 쓰지 않고, 업무 로직·모델 호출은 FastAPI에 둡니다.

## 코드 스타일 요약

- 프론트: 컴포넌트 파일 PascalCase, 훅·유틸 camelCase, 라우트 폴더 kebab-case. 라우트 파일 외 컴포넌트는 `export const` 화살표 함수, 한 파일 한 컴포넌트, Props는 `{Component}Props` interface. `@/` 절대 경로. 쿼리 키는 `lib/queryKeys.ts`, SSE 이름은 `shared/sse-events.json`.
- 백엔드: snake_case 모듈·함수, PascalCase 클래스, 테이블은 snake_case 복수형, API 경로는 kebab-case 복수형, Pydantic 모델은 `Read`/`Create`/`Update` 접미사.
- AI: 도구 이름은 `동사_명사`, 그래프 노드는 snake_case 동사형, 양식 스키마는 `app/schemas/forms/`에 양식당 한 파일, 규칙표 행마다 출처 URL·출처 날짜·검수자·검수일.

## Git

- 브랜치: `feat|fix|hotfix/#이슈번호-내용`, develop에서 분기해 develop으로 PR (hotfix만 main).
- 커밋·PR 제목: `type(scope): 무엇을 왜` — type `feat|fix|refactor|style|design|docs|test|chore|ci`, scope `fe|be|ai|infra|docs`. 호환성 깨짐은 `type(scope)!:`.
- main·develop에 직접 push하지 않습니다. 한 PR은 한 영역, +1000줄 이내.
