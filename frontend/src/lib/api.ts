/**
 * 브라우저에서 서버를 부르는 유일한 창구입니다. 모든 요청은 같은 사이트의 BFF(/api/*)로 갑니다.
 * 실패 응답은 ApiError 하나로 바꿔 던지고, 모의 응답 모드에 따라 요청을 mock(src/mocks)으로 돌리기도 합니다.
 * 백엔드에 구현된 경로는 BACKEND_ROUTES에 적어 두며, 기능을 구현할 때마다 경로를 더하고 그 mock을 지웁니다.
 */

import type { components } from '@/types/api.gen';
import { resolveMock } from '@/mocks/handlers';

/** 브라우저는 같은 사이트의 BFF(`src/app/api/[...path]/route.ts`)만 부릅니다. 백엔드 주소는 서버만 압니다. */
export const API_BASE_URL = '/api';

/**
 * 모의 응답 모드 (`NEXT_PUBLIC_USE_MOCK`).
 * - `1`: 전부 `src/mocks/` 스냅샷 (백엔드 없이 화면만 볼 때)
 * - `0`: 전부 실제 백엔드
 * - 그 밖(비움·`hybrid`): 아래 `BACKEND_ROUTES`만 실제 백엔드, 나머지는 mock
 */
const MOCK_MODE = process.env.NEXT_PUBLIC_USE_MOCK ?? '';
export const IS_MOCK_API = MOCK_MODE === '1';
const IS_REAL_ONLY = MOCK_MODE === '0';

/**
 * 백엔드에 구현된 경로. 기능 PR에서 백엔드를 구현하면 여기에 경로를 더하고 그 mock을 지웁니다.
 * 계정 입장 이후 mock은 저장된 세션의 persona_id로 이어서 응답합니다.
 */
const BACKEND_ROUTES: RegExp[] = [
  /^\/health$/,
  /^\/personas$/,
  /^\/accounts\/[^/]+$/,
  /^\/accounts\/[^/]+\/resume$/,
];

/** 이 경로를 mock으로 돌릴지. 혼합 모드에서는 `BACKEND_ROUTES`에 없는 경로만 mock입니다. */
export const usesMock = (path: string): boolean => {
  if (IS_MOCK_API) return true;
  if (IS_REAL_ONLY) return false;
  const pathname = path.split('?')[0];
  return !BACKEND_ROUTES.some((route) => route.test(pathname));
};

export type ErrorCode = components['schemas']['ErrorCode'];
type ErrorResponse = components['schemas']['ErrorResponse'];

// 서버에 닿지 못했을 때(네트워크 끊김 등) 쓰는 코드. 서버 ErrorCode와 겹치지 않게 둡니다.
export type ClientErrorCode = ErrorCode | 'NETWORK_ERROR';

const FALLBACK_MESSAGE = '일시적인 문제가 생겼어요. 잠시 후 다시 시도해 주세요.';
const NETWORK_MESSAGE = '인터넷 연결을 확인하고 다시 시도해 주세요.';

/** 모든 API 실패는 이 오류로 던집니다. 화면에는 message를 그대로 보여주고, 필요할 때만 code로 분기합니다. */
export class ApiError extends Error {
  constructor(
    readonly code: ClientErrorCode,
    message: string,
    readonly status: number,
    readonly details: unknown = null,
    readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const isErrorResponse = (body: unknown): body is ErrorResponse =>
  typeof body === 'object' &&
  body !== null &&
  typeof (body as ErrorResponse).code === 'string' &&
  typeof (body as ErrorResponse).message === 'string';

/** 서버에 닿지 못했을 때(네트워크 끊김 등) 던지는 오류. 호출부에서 공통으로 씁니다. */
export const networkError = (): ApiError => new ApiError('NETWORK_ERROR', NETWORK_MESSAGE, 0);

/** 실패 응답(`!res.ok`)을 공통 ApiError로 바꿉니다. 본문이 공통 형식이 아니면 INTERNAL_ERROR로 둡니다. */
export const toApiError = async (res: Response): Promise<ApiError> => {
  const requestId = res.headers.get('X-Request-ID');
  const body: unknown = await res.json().catch(() => null);
  if (isErrorResponse(body)) {
    return new ApiError(body.code, body.message, res.status, body.details ?? null, requestId);
  }
  return new ApiError('INTERNAL_ERROR', FALLBACK_MESSAGE, res.status, null, requestId);
};

export const apiFetch = async <T>(path: string, init?: RequestInit): Promise<T> => {
  if (usesMock(path)) return resolveMock<T>(path, init);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw networkError();
  }
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
};

/**
 * 파일 올리기 (`POST /files`, 2-0.4). multipart라 Content-Type을 직접 넣지 않습니다 (브라우저가 boundary를 붙임).
 * 모의 모드에서는 FormData 그대로 `resolveMock`에 넘깁니다.
 */
export const apiUpload = async <T>(path: string, file: File, signal?: AbortSignal): Promise<T> => {
  const form = new FormData();
  form.append('file', file);
  if (usesMock(path)) return resolveMock<T>(path, { method: 'POST', body: form, signal });

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method: 'POST',
      body: form,
      signal,
    });
  } catch {
    throw networkError();
  }
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
};
