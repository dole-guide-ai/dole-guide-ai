---
paths:
  - "frontend/**"
---

# 프론트 작성 규칙

상세 표는 `docs/CONVENTIONS.md` 4·7절. Next.js 16 API는 `frontend/node_modules/next/dist/docs/`로 확인.

## 폴더

| 위치 | 둘 것 |
| --- | --- |
| `src/app/` | 라우트 파일(`page.tsx`, `layout.tsx`)만. 화면 조립만 하고 로직은 features로. 계정 화면은 `/p/[personaId]/...` |
| `src/app/api/**/route.ts` | BFF만. 쿠키 → `Authorization: Bearer`, 공유 비밀 헤더, 스트림 그대로 전달 (`src/lib/bff.ts`) |
| `src/features/<기능>/` | 기능별 컴포넌트·훅·테스트를 함께 (견본: `features/health/`) |
| `src/components/` | 두 기능 이상에서 쓰는 공용 UI |
| `src/lib/` | `api.ts`(호출·`ApiError`), `queryKeys.ts`, `sse.ts` |
| `src/test/` | `renderWithProviders`, `mockFetch` |

## 데이터

- 서버 호출은 `apiFetch`(`lib/api.ts`)만. 컴포넌트에서 `fetch` 직접 호출 금지. 브라우저는 같은 사이트 `/api/...`(BFF)만 부르고 백엔드 주소를 모름.
- 계정 데이터 경로는 `/accounts/{personaId}/...`. 쿼리 키도 `personaId` 기준.
- 서버 데이터는 TanStack Query 훅(`features/<기능>/useXxx.ts`)으로. 쿼리 키는 `lib/queryKeys.ts`.
- 요청·응답 타입은 `@/types/api.gen`의 `components['schemas'][...]`만. 직접 타입을 다시 정의하지 않음. `api.gen.ts`는 수정 금지(`pnpm gen:api`).
- SSE 이벤트 이름은 `SSE_EVENTS`(`lib/sseEvents.ts`). 스트림 오류는 `error` 이벤트.
- JSON 본문 쓰기 요청은 `apiSend(path, method, body)`, 응답 `{updates}`는 `applyFormUpdates`로 적용.
- 앱 코드에 mock을 두지 않음. 화면은 늘 실제 백엔드(BFF)를 부름. 테스트는 `src/test/fixtures`(실제 응답을 떠 둔 JSON)와 `mockFetch`로 fetch만 바꿈. 기능 코드에서 `process.env`를 읽지 않음(서버 전용 값은 `lib/serverConfig.ts`).

## 상수·반복 코드 (가독성)

- 숫자·식별 문자열을 코드에 직접 쓰지 않고 이름 붙인 상수로 한 곳에 둠.

| 무엇 | 위치 |
| --- | --- |
| API 경로 | `lib/apiPaths.ts` (`API_PATHS`, 기능 훅과 mock이 같이 씀) |
| 쿼리 키 · 캐시 시간 | `lib/queryKeys.ts` · `lib/queryConfig.ts` (`STALE_TIME`) |
| 오류 코드 | `lib/errorCodes.ts` (`ERROR_CODES`) |
| SSE 이벤트 · 대화 액션 · 역할 · 입력 방식 | `lib/sseEvents.ts` · `features/chat/chatActions.ts` · `CHAT_ROLE` · `INPUT_KIND` |

- 같은 로직이 두 곳 이상이면 순수 함수(`lib/`)나 공용 훅으로 뺌. 예: `apiSend`, `applyFormUpdates`, `useProcedurePatch`.
- 상수 객체는 `as const`, 타입은 `(typeof X)[keyof typeof X]`로 만들어 값과 타입을 한 번만 씀.

## 오류 처리

- 실패는 `ApiError`로 옴. 화면에는 `error.message`를 그대로 보여줌(백엔드가 쓴 한국어).
- 특별 처리가 필요할 때만 `error.code`로 분기 (`RATE_LIMITED` → 다시 시도 안내, `NETWORK_ERROR` → 연결 안내).
- 오류 화면에 `requestId`를 작게 표시해도 됨(문의용). 입력값을 오류 문구에 넣지 않음.

## 개인정보 (데모)

- 이름·전화번호·주민등록번호 입력란을 만들지 않음. 기본정보·계좌는 서버가 주는 표시값(seed 고정)만 보여줌. 입력 화면에 "개인정보를 입력하지 마세요(데모)" 안내.
- `console.log`로 사용자 입력·응답 원문을 찍지 않음. localStorage에 대화 원문 저장 금지.

## 테스트

- 대상 옆에 `*.test.tsx`/`*.test.ts`. 렌더는 `renderWithProviders`, API는 `mockFetchJson`.
- 성공·로딩·오류(`ApiError` message 표시) 상태를 확인.
