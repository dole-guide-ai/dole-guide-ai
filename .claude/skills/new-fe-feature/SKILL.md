---
name: new-fe-feature
description: 프론트에 새 화면 기능(데이터 조회·입력 UI)을 추가할 때 사용. features/<기능>/ 아래 쿼리 훅·컴포넌트·테스트를 이 레포 규칙대로 만든다.
---

# 프론트 기능 추가

규칙: `.claude/rules/frontend.md`, `docs/CONVENTIONS.md` 4·7절. Next.js 16 API는 `frontend/node_modules/next/dist/docs/`로 확인. 명령은 `frontend/`에서 실행.

1. **API 타입 확인** — 백엔드 API가 먼저 있어야 한다. 루트에서 `pnpm gen:api` 후 `@/types/api.gen`의 `components['schemas']['XxxRead']`를 쓴다. 타입을 직접 다시 정의하지 않는다.
2. **쿼리 키** — `src/lib/queryKeys.ts`에 키 추가.
3. **훅** — `src/features/<기능>/use<대상><동작>.ts`. `useQuery`/`useMutation` + `apiFetch`(`@/lib/api`). `fetch` 직접 호출 금지(ESLint가 막음). 변경 후 관련 쿼리 무효화.
4. **컴포넌트** — `src/features/<기능>/<Name>.tsx`, `export const` 화살표 함수, Props는 `<Name>Props` interface. 로딩·오류·빈 상태를 모두 그린다.
   - 오류는 `error instanceof ApiError`이면 `error.message`를 그대로 표시, 필요한 `code`만 분기(`RATE_LIMITED`, `NETWORK_ERROR`).
   - 중장년 사용자: 큰 글씨, 분명한 버튼 문구, 쉬운 문장. 개인정보 입력란 금지, 입력 화면에 "개인정보를 입력하지 마세요(데모)".
   - Tailwind v4 문법만.
5. **라우트** — 필요하면 `src/app/<kebab-case>/page.tsx`에서 컴포넌트를 조립만 한다.
6. **테스트** — 대상 옆 `<Name>.test.tsx`. `renderWithProviders` + `mockFetchJson`으로 성공·오류(`{code, message}` 응답 → message 표시) 상태를 확인. 합성 데이터만.
7. **마무리** — 루트에서 `pnpm check:fe`.

견본: `src/features/health/`(`useHealth.ts`, `HealthStatus.tsx`, `HealthStatus.test.tsx`), `src/lib/api.test.ts`.
