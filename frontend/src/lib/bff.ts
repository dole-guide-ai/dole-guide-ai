/**
 * Next 서버에서 백엔드로 요청을 넘기는 BFF 로직입니다. Route Handler에서만 쓰고 브라우저 번들에는 들어가지 않습니다.
 * 브라우저의 HttpOnly 쿠키에 든 방문자 토큰을 Authorization 헤더로 바꾸고, 공유 비밀 헤더를 붙여 백엔드를 부릅니다.
 * 쿠키가 없거나 토큰이 만료됐으면 방문자를 새로 만들어 쿠키를 심고, 응답 본문은 스트림 그대로 돌려줍니다.
 */

import { type NextRequest, NextResponse } from 'next/server';

export const VISITOR_COOKIE = 'dole_visitor';
export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;

const COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60;
const FORWARD_REQUEST_HEADERS = [
  'accept',
  'content-type',
  'if-match',
  'idempotency-key',
  'x-request-id',
];
const FORWARD_RESPONSE_HEADERS = [
  'cache-control',
  'content-disposition',
  'content-type',
  'etag',
  'location',
  'x-request-id',
];
// 브라우저가 직접 부르면 안 되는 백엔드 경로 (토큰이 본문으로 나옴)
const BLOCKED_PATHS = new Set(['visitors']);

const backendBase = () => process.env.API_BASE_URL ?? 'http://localhost:8000';
const internalSecret = () => process.env.BACKEND_INTERNAL_SECRET ?? '';

const errorJson = (status: number, code: string, message: string) =>
  NextResponse.json({ code, message, details: null }, { status });

const backendHeaders = (token: string | null, from?: Headers): Headers => {
  const headers = new Headers();
  if (from) {
    for (const name of FORWARD_REQUEST_HEADERS) {
      const value = from.get(name);
      if (value) headers.set(name, value);
    }
  }
  const secret = internalSecret();
  if (secret) headers.set('X-Internal-Secret', secret);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  return headers;
};

const createVisitor = async (signal: AbortSignal): Promise<string | null> => {
  const res = await fetch(`${backendBase()}/visitors`, {
    method: 'POST',
    headers: backendHeaders(null),
    signal,
    cache: 'no-store',
  });
  if (!res.ok) return null;
  const body = (await res.json()) as { visitor_token: string };
  return body.visitor_token;
};

const forward = (request: NextRequest, target: string, token: string, body: BodyInit | null) =>
  fetch(target, {
    method: request.method,
    headers: backendHeaders(token, request.headers),
    body,
    signal: request.signal,
    cache: 'no-store',
    // 요청 본문을 스트림으로 넘길 때 필요합니다 (Node fetch).
    ...(body ? { duplex: 'half' } : {}),
  } as RequestInit);

const toClientResponse = (upstream: Response, setToken: string | null): NextResponse => {
  const headers = new Headers();
  for (const name of FORWARD_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (!value) continue;
    // 백엔드 Location(/accounts/park)을 브라우저가 쓰는 주소(/api/accounts/park)로 바꿉니다.
    headers.set(name, name === 'location' && value.startsWith('/') ? `/api${value}` : value);
  }
  const response = new NextResponse(upstream.status === 204 ? null : upstream.body, {
    status: upstream.status,
    headers,
  });
  if (setToken) {
    response.cookies.set(VISITOR_COOKIE, setToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: COOKIE_MAX_AGE_SECONDS,
    });
  }
  return response;
};

const isUnauthorizedVisitor = async (res: Response) => {
  if (res.status !== 401) return false;
  const body = (await res
    .clone()
    .json()
    .catch(() => null)) as { code?: string } | null;
  return body?.code === 'UNAUTHORIZED';
};

/** `/api/<path>` 요청을 백엔드 `/<path>`로 넘깁니다. 쿠키가 없거나 만료면 방문자를 새로 만듭니다. */
export const proxyToBackend = async (request: NextRequest, path: string[]): Promise<Response> => {
  if (path.length === 0 || BLOCKED_PATHS.has(path[0])) {
    return errorJson(404, 'NOT_FOUND', '찾는 정보가 없어요.');
  }
  const length = Number(request.headers.get('content-length') ?? 0);
  if (length > MAX_UPLOAD_BYTES) {
    return errorJson(413, 'FILE_TOO_LARGE', '파일이 너무 커요. 4MB 이하로 올려 주세요.');
  }

  const target = `${backendBase()}/${path.map(encodeURIComponent).join('/')}${request.nextUrl.search}`;
  const hasBody = !['GET', 'HEAD'].includes(request.method);
  let token = request.cookies.get(VISITOR_COOKIE)?.value ?? null;
  let issued: string | null = null;
  try {
    // 토큰이 만료되면 한 번 다시 보내야 하므로 본문은 미리 읽어 둡니다(최대 4MB).
    // 읽다가 끊기면 아래 catch에서 499·502로 처리합니다.
    const body = hasBody ? await request.arrayBuffer() : null;
    // content-length 없이 오는 본문도 있으므로 실제로 읽은 크기로 한 번 더 확인합니다.
    if (body && body.byteLength > MAX_UPLOAD_BYTES) {
      return errorJson(413, 'FILE_TOO_LARGE', '파일이 너무 커요. 4MB 이하로 올려 주세요.');
    }
    if (!token) {
      token = issued = await createVisitor(request.signal);
      if (!token) return errorJson(503, 'INTERNAL_ERROR', '잠시 후 다시 시도해 주세요.');
    }
    let upstream = await forward(request, target, token, body);
    if (!issued && (await isUnauthorizedVisitor(upstream))) {
      token = issued = await createVisitor(request.signal);
      if (!token) return toClientResponse(upstream, null);
      upstream = await forward(request, target, token, body);
    }
    return toClientResponse(upstream, issued);
  } catch (error) {
    if (request.signal.aborted) return new Response(null, { status: 499 });
    console.error('bff proxy failed', error instanceof Error ? error.name : 'unknown');
    return errorJson(
      502,
      'INTERNAL_ERROR',
      '일시적인 문제가 생겼어요. 잠시 후 다시 시도해 주세요.',
    );
  }
};
