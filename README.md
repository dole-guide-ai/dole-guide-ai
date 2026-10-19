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

도구 버전은 [`mise.toml`](mise.toml) 한 곳에서 관리합니다. (Node 22, pnpm 10.34, Python 3.14, uv 0.12)

| 설치 | macOS | Windows (PowerShell) |
| --- | --- | --- |
| Git | 기본 설치 | Git for Windows |
| mise | `brew install mise` | `winget install jdx.mise` |
| Docker | Docker Desktop | Docker Desktop (WSL2 백엔드) |

mise를 셸에 연결합니다(한 번). macOS(zsh)는 `~/.zshrc`에 `eval "$(mise activate zsh)"`, Windows는 PowerShell 프로필에 `(&mise activate pwsh) | Out-String | Invoke-Expression`을 추가하고 터미널을 다시 엽니다.

명령은 macOS 터미널과 Windows PowerShell에서 똑같이 동작합니다. Docker Desktop을 켠 뒤 레포 루트에서 처음 한 번:

```bash
mise trust
```

```bash
mise install
```

```bash
pnpm bootstrap
```

`mise install`이 Node·pnpm·Python·uv를 정해진 버전으로 설치합니다. 버전을 올릴 때 같이 맞춰야 하는 파일은 `AGENTS.md`에 정리돼 있습니다.

의존성 설치(프론트·백엔드·Git 훅) → `backend/.env`, `frontend/.env.local` 생성(없을 때만, 각 폴더의 `.env.example` 복사) → DB 실행 → 마이그레이션까지 합니다. LLM 키는 `backend/.env`에 직접 채우세요. 비어 있으면 서버는 뜨고 시작할 때 경고만 합니다. `APP_ENV`가 `local`이 아니면 키가 없을 때 서버가 시작되지 않습니다.

```bash
pnpm dev:be           # http://localhost:8000/docs
pnpm dev:fe           # http://localhost:3000
```

### Windows 참고

- 줄바꿈은 `.gitattributes`로 LF 고정입니다. 처음 클론하기 전에 `git config --global core.autocrlf false`를 권장합니다. 이미 클론했다면 `git add --renormalize .`
- Python이 한글 파일·로그를 UTF-8로 다루도록 `PYTHONUTF8=1` 환경변수를 설정하세요. (`setx PYTHONUTF8 1` 후 터미널 재시작)
- Git 훅(lefthook)은 Git for Windows의 sh로 실행됩니다. Git for Windows를 설치하면 별도 설정이 필요 없습니다.
- 경로가 긴 패키지 설치 오류가 나면 `git config --global core.longpaths true`

## 자주 쓰는 명령

| 명령 | 설명 |
| --- | --- |
| `pnpm gen:api` (루트) | 백엔드 OpenAPI → `frontend/src/types/api.gen.ts` 재생성 |
| `pnpm lint` / `pnpm format` / `pnpm typecheck` (frontend) | 린트·포맷·타입 검사 |
| `uv run ruff check .` / `uv run ruff format .` / `uv run pytest` (backend) | 린트·포맷·테스트 |
| `uv run alembic revision --autogenerate -m "메시지"` (backend) | 마이그레이션 생성 |
| `docker compose --profile full up -d --build` | DB + 백엔드 함께 실행 |

## 테스트

```bash
pnpm dev:db        # integration 테스트용 DB
pnpm test          # FE + BE 테스트
pnpm check         # PR 전 전체 검사
pnpm test:eval     # AI 평가 세트
pnpm check:pr-size # PR 추가 줄 수(+1000 이내) 확인
```

자세한 구조는 `AGENTS.md`의 테스트 절을 참고하세요.

## Git 훅 (lefthook)

- pre-commit: 스테이징된 파일에 ESLint·Prettier(frontend), ruff(backend) 자동 수정
- commit-msg: `type(scope): 내용` 형식 검사
- pre-push: 바뀐 영역의 단위 테스트(FE vitest, BE unit)

## CI

| 워크플로 | 검사 |
| --- | --- |
| frontend | 린트·포맷·타입·테스트·빌드 (`frontend/**` 변경 시) |
| backend | uv.lock 동기화·ruff·마이그레이션·pytest, api.gen.ts 재생성 여부 (`backend/**` 변경 시) |
| security | gitleaks로 커밋에 들어간 비밀값 검사 |
| pr-title | PR 제목 `type(scope): 내용` |
| pr-size | 추가 줄 수 +1000 이내 (lock·api.gen.ts·마이그레이션 제외) |

같은 브랜치에 새로 push하면 진행 중인 이전 실행은 취소됩니다.

## 배포

- 프론트: Vercel (Root Directory = `frontend`, "Include files outside the root directory" 켜둠 — `shared/` 사용)
- 백엔드: AWS Lightsail 서버 한 대에 Docker Compose로 백엔드 + Postgres(pgvector) + Caddy(HTTPS)를 띄웁니다.
  - 운영 구성: `docker-compose.yml` + `docker-compose.prod.yml` (DB·앱 포트는 외부 비공개, 80·443만 공개)
  - 서버 첫 세팅: `deploy/server-setup.sh`, 서버 설정 템플릿: `deploy/.env.example`, HTTPS: `deploy/Caddyfile`
  - 배포: GitHub Actions `deploy-server` (SSH → git pull → 빌드·재시작 → 마이그레이션 → 헬스 체크). 첫 배포 확인 전까지 수동 실행만 켜져 있습니다.
  - 따라 하기 가이드: 노션 「백엔드 배포 가이드」
