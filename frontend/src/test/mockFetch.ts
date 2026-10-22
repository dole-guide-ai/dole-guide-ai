import { vi } from 'vitest';

// API 호출은 fetch를 대체해 테스트합니다. 실제 서버로 요청을 보내지 않습니다.
export const mockFetchJson = (body: unknown, init: ResponseInit = { status: 200 }) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      ...init,
      headers: { 'Content-Type': 'application/json' },
    }),
  );

// 응답이 오지 않는 요청(로딩 상태를 붙잡아 두는 테스트용)
export const mockFetchPending = () =>
  vi.spyOn(globalThis, 'fetch').mockReturnValue(new Promise(() => {}));
