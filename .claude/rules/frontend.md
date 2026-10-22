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
- SSE 이벤트 이름은 `SSE_EVENTS`(`lib/sse.ts`). 스트림 오류는 `error` 이벤트.

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
