# dole-guide-ai

말로 이야기하면 AI가 고용24 이력서와 실업인정 신청서를 양식 그대로 완성해 주는 중장년층 실업급여 행정 도우미입니다.

## 구조

| 경로 | 내용 |
| --- | --- |
| `frontend/` | Next.js (App Router) · pnpm · Vercel |
| `backend/` | FastAPI · SQLAlchemy · Alembic · LangGraph · uv |
| `shared/sse-events.json` | 프론트·백엔드 공통 SSE 이벤트 이름 |
| `docs/CONVENTIONS.md` | 브랜치·커밋·코드 컨벤션 |

## 로컬 실행

필요 도구: Node 22+, pnpm 10, uv, Docker

```bash
cp .env.example backend/.env           # backend 항목만 남기고 값 채우기
docker compose up -d db
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
```

```bash
cd frontend && pnpm install && pnpm dev
```

## 자주 쓰는 명령

| 명령 | 설명 |
| --- | --- |
| `pnpm gen:api` (루트) | 백엔드 OpenAPI → `frontend/src/types/api.gen.ts` 재생성 |
| `pnpm lint` / `pnpm format` / `pnpm typecheck` (frontend) | 린트·포맷·타입 검사 |
| `uv run ruff check .` / `uv run ruff format .` / `uv run pytest` (backend) | 린트·포맷·테스트 |
| `uv run alembic revision --autogenerate -m "메시지"` (backend) | 마이그레이션 생성 |
| `docker compose --profile full up -d --build` | DB + 백엔드 함께 실행 |
