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

/** `mockFetchRoutes`에서 응답을 보내지 않고 붙잡아 둘 경로에 씁니다. */
export const PENDING = Symbol('pending');

/**
 * 요청 URL별로 응답을 나눕니다. 값은 JSON 본문이고, `{ status, body }`면 그 상태 코드로 보냅니다.
 * 목록에 없는 요청은 바로 실패시켜, 테스트가 예상하지 못한 호출을 놓치지 않게 합니다.
 */
export const mockFetchRoutes = (routes: [RegExp, unknown][]) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    const route = routes.find(([pattern]) => pattern.test(url));
    if (!route) throw new Error(`예상하지 않은 요청: ${url}`);
    const [, response] = route;
    if (response === PENDING) return new Promise<Response>(() => {});
    if (response && typeof response === 'object' && 'status' in response && 'body' in response) {
      const { status, body } = response as { status: number; body: unknown };
      return Response.json(body, { status });
    }
    return Response.json(response);
  });
