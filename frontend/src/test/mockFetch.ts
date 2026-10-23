import { vi } from 'vitest';

// API 호출은 fetch를 대체해 테스트합니다. 실제 서버로 요청을 보내지 않습니다.
export const mockFetchJson = (body: unknown, init: ResponseInit = { status: 200 }) =>
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify(body), {
      ...init,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
