# 개발 컨벤션

## 1. 브랜치 전략 (축소판 Git Flow)

| 브랜치 | 역할 | 분기 → 머지 |
| --- | --- | --- |
| `main` | 배포. 머지 시 자동 배포 | develop에서만 머지 |
| `develop` | 개발 통합 | 기능 브랜치가 모이는 곳 |
| `feat/#이슈번호-내용` | 기능 개발 | develop → develop |
| `fix/#이슈번호-내용` | 버그 수정 | develop → develop |
| `hotfix/#이슈번호-내용` | 배포 후 긴급 수정 | main → main, 이후 develop에도 반영 |

예시: `feat/#12-chat-stream`, `fix/#21-round-missing`, `hotfix/#30-login-500`

- main, develop은 직접 push하지 않습니다. PR, 리뷰 2명 이상, CI 통과를 필수로 합니다.
- 기능 브랜치 → develop, develop → main 모두 Merge commit으로 합니다. (Rebase, Squash Merge 사용 x)
- main 머지 시 Vercel 운영 배포가 자동으로 실행됩니다. develop과 PR은 Vercel 미리보기로 확인합니다.
- EC2 배포(GitHub Actions `deploy-ec2`)는 AWS 준비 전까지 수동 실행만 켜져 있고, 준비되면 main 머지 시 자동 실행으로 바꿉니다.
- main 머지 시 버전 태그(`v0.1.0`)를 붙입니다. 문제가 생기면 이전 태그로 되돌립니다.
- 한 이슈에 한 PR, PR은 +1000줄 이내. 자동 생성 파일(`api.gen.ts`, lock 파일, 자동 생성 마이그레이션)은 줄 수에서 제외합니다.

## 2. 커밋 · PR · 이슈

형식: `type(scope): 무엇을 왜`

| type | 용도 |
| --- | --- |
| feat | 기능 추가 |
| fix | 버그 수정 |
| refactor | 동작 변화 없는 코드 개선 (파일명 변경, 삭제 포함) |
| style | 포맷·린트만 수정 |
| design | UI·스타일 변경 |
| docs | 문서 수정 |
| test | 테스트·평가 세트 추가 및 수정 |
| chore | 설정·패키지·빌드 |
| ci | GitHub Actions·배포 설정 |

| scope | 대상 폴더 |
| --- | --- |
| fe | `frontend/` |
| be | `backend/` (agent 제외) |
| ai | `backend/app/agent/`, `backend/evals/`, `backend/data/rules/` |
| infra | `docker-compose.yml`, `.github/workflows/` |
| docs | 문서 |

```
feat(ai): 실업인정 신청서 슬롯 필링 서브그래프 추가
fix(be): 절차 상태 조회 시 회차 누락 수정
feat(ai)!: 에이전트 상태 필드 구조 변경
```

- 큰 호환성 변경은 type 뒤에 `!`를 붙입니다.
- PR·이슈 제목은 커밋과 같은 형식, 접두어는 소문자 (`pr-title` 워크플로가 검사).
- PR 본문: 관련 이슈(`closes #12`), 변경 내용, 확인 방법. AI 영역 PR은 평가 결과 첨부.

## 3. 모노레포 규칙

- CI는 경로 필터로 나눕니다. frontend 변경 시 FE 린트·포맷·타입 검사·테스트·빌드를, backend 변경 시 uv.lock 동기화·ruff 린트·포맷·마이그레이션·pytest와 `api.gen.ts` 재생성 여부를 검사합니다.
- 백엔드 API를 바꾸면 루트에서 `pnpm gen:api`로 `api.gen.ts`를 다시 생성해 같은 PR에 포함합니다.
- 패키지 관리는 프론트 pnpm, 백엔드 uv로 고정합니다.
- 한 PR은 한 영역. API 변경처럼 프론트·백엔드가 함께 바뀌는 경우만 한 PR에 담습니다.

## 4. 프론트엔드

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 컴포넌트·컴포넌트 파일 | PascalCase, 파일명 = 컴포넌트명 | `ChatPanel.tsx` |
| 훅·유틸·타입 파일 | camelCase | `useChatStream.ts`, `chat.types.ts` |
| 라우트 폴더 | kebab-case | `app/recognition-form/` |
| 함수·변수 | camelCase | `userName` |
| 상수 | UPPER_SNAKE_CASE | `API_BASE_URL` |
| 타입·인터페이스 | PascalCase, interface 우선 | `FormDraft` |
| Props | `{Component}Props` | `ChatPanelProps` |
| Boolean | `is`, `has` 접두사 | `isLoading` |
| 핸들러 | 내부 `handle~`, Props `on~` | `handleSubmit`, `onSubmit` |
| 쿼리 훅 | `use` + 대상 + 동작 | `useRecognitionForm`, `useSubmitForm` |

- 라우트 파일(`page.tsx`, `layout.tsx` 등)은 `export default function`. 그 외 컴포넌트는 화살표 함수 + `export const`, 한 파일에 한 컴포넌트.
- Props는 구조 분해, early return 사용. `'use client'`는 상태·이벤트가 있는 컴포넌트에만.
- 서버 렌더링·Next.js 캐시를 쓰지 않고, 업무 로직과 모델 호출은 FastAPI에 둡니다.
- API 타입은 `api.gen.ts`만, 쿼리 키는 `lib/queryKeys.ts`, SSE 이벤트 이름은 `shared/sse-events.json`.
- 절대 경로(`@/`). import 순서(React·Next → 외부 → 내부 컴포넌트 → 유틸·타입 → 에셋)는 ESLint가, Tailwind 클래스 순서는 Prettier가 정렬합니다.
- 라우팅은 `next/navigation`.

## 5. 백엔드

| 대상 | 규칙 | 예시 |
| --- | --- | --- |
| 파일·모듈 | snake_case | `procedure_service.py` |
| 함수·변수 | snake_case | `get_procedure_state` |
| 클래스 | PascalCase | `ProcedureState` |
| 상수 | UPPER_SNAKE_CASE | `MAX_ASK_COUNT` |
| DB 테이블 | snake_case 복수형 | `procedure_states` |
| API 경로 | kebab-case 복수형 | `/forms/{kind}/review` |
| Pydantic 모델 | 용도 접미사 | `FormDraftRead`, `FormDraftUpdate` |

- 호출 방향은 라우터 → 서비스 → 레포지토리 한 방향. 라우터에는 HTTP 처리만.
- 조건·벡터·키워드를 합치는 검색 쿼리는 레포지토리에 SQL로 직접 작성합니다.
- 마이그레이션은 Alembic으로만, 메시지 필수. 마이그레이션 파일은 PR에서 따로 확인합니다.
- 로그에 이름, 연락처, 발화 원문 등 개인정보를 남기지 않습니다.
- 비밀값은 `.env`와 GitHub Secrets에만 둡니다.

## 6. AI

| 대상 | 규칙 |
| --- | --- |
| 프롬프트 | `app/agent/prompts/`에 파일로 둠. 변경 시 PR 리뷰 |
| 모델명 | 코드에 직접 쓰지 않고 설정(`.env`)에서만 지정. 호출은 `app/agent/gateway` 경유 |
| 도구 이름 | snake_case 동사_명사 |
| 그래프 노드 | snake_case 동사형 |
| 양식 스키마 | `app/schemas/forms/`에 양식당 파일 하나 |
| 규칙표 | `data/rules/`, 행마다 출처 URL·출처 날짜·검수자·검수일 필수 |
| 평가 세트 | `evals/`에 시나리오별. 모델·프롬프트·규칙표 변경 PR에 평가 결과 첨부 |
| 실험 코드 | `experiments/`, 서비스 코드에서 import 금지 |
| 시험 데이터 | 실제 개인정보 금지, 합성 데이터만 |
