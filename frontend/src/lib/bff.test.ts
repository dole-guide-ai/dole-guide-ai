import { NextRequest } from 'next/server';

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MAX_UPLOAD_BYTES, proxyToBackend, VISITOR_COOKIE } from '@/lib/bff';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('proxyToBackend', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    vi.stubEnv('API_BASE_URL', 'http://backend.test');
    vi.stubEnv('BACKEND_INTERNAL_SECRET', 'synthetic-secret');
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('쿠키 토큰을 Bearer로, 공유 비밀을 헤더로 넘긴다', async () => {
    fetchMock.mockResolvedValueOnce(json({ items: [], total: 0 }));
    const request = new NextRequest('http://localhost/api/personas', {
      headers: { cookie: `${VISITOR_COOKIE}=tok-1` },
    });

    const res = await proxyToBackend(request, ['personas']);

    expect(res.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(url).toBe('http://backend.test/personas');
    expect(headers.get('authorization')).toBe('Bearer tok-1');
    expect(headers.get('x-internal-secret')).toBe('synthetic-secret');
  });

  it('쿠키가 없으면 방문자를 만들고 HttpOnly 쿠키를 심는다', async () => {
    fetchMock
      .mockResolvedValueOnce(json({ visitor_token: 'new-tok', expires_at: '2026-10-29' }, 201))
      .mockResolvedValueOnce(json({ items: [], total: 0 }));
    const request = new NextRequest('http://localhost/api/personas');

    const res = await proxyToBackend(request, ['personas']);

    expect(fetchMock.mock.calls[0][0]).toBe('http://backend.test/visitors');
    const cookie = res.headers.get('set-cookie') ?? '';
    expect(cookie).toContain(`${VISITOR_COOKIE}=new-tok`);
    expect(cookie.toLowerCase()).toContain('httponly');
    expect(await res.text()).not.toContain('new-tok');
  });

  it('토큰이 만료돼 401이면 새 방문자로 한 번 다시 보낸다', async () => {
    fetchMock
      .mockResolvedValueOnce(json({ code: 'UNAUTHORIZED', message: 'x' }, 401))
      .mockResolvedValueOnce(json({ visitor_token: 'fresh', expires_at: '2026-10-29' }, 201))
      .mockResolvedValueOnce(json({ items: [], total: 0 }));
    const request = new NextRequest('http://localhost/api/personas', {
      headers: { cookie: `${VISITOR_COOKIE}=old` },
    });

    const res = await proxyToBackend(request, ['personas']);

    expect(res.status).toBe(200);
    expect(res.headers.get('set-cookie')).toContain(`${VISITOR_COOKIE}=fresh`);
  });

  it('Location을 /api 기준으로 바꾼다', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('{}', { status: 201, headers: { location: '/accounts/park' } }),
    );
    const request = new NextRequest('http://localhost/api/accounts/park', {
      method: 'PUT',
      headers: { cookie: `${VISITOR_COOKIE}=tok` },
    });

    const res = await proxyToBackend(request, ['accounts', 'park']);

    expect(res.headers.get('location')).toBe('/api/accounts/park');
  });

  it('방문자 발급 경로는 브라우저에 열지 않는다', async () => {
    const res = await proxyToBackend(new NextRequest('http://localhost/api/visitors'), [
      'visitors',
    ]);

    expect(res.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('4MB를 넘는 본문은 413', async () => {
    const request = new NextRequest('http://localhost/api/accounts/park/files', {
      method: 'POST',
      headers: { 'content-length': String(MAX_UPLOAD_BYTES + 1) },
    });

    const res = await proxyToBackend(request, ['accounts', 'park', 'files']);

    expect(res.status).toBe(413);
    expect((await res.json()).code).toBe('FILE_TOO_LARGE');
  });

  it('content-length가 없어도 실제 본문이 4MB를 넘으면 413', async () => {
    const request = new NextRequest('http://localhost/api/accounts/park/files', {
      method: 'POST',
      body: new Uint8Array(MAX_UPLOAD_BYTES + 1),
    });
    request.headers.delete('content-length');

    const res = await proxyToBackend(request, ['accounts', 'park', 'files']);

    expect(res.status).toBe(413);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
