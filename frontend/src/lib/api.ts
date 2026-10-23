import { ERROR_CODES } from '@/lib/errorCodes';
/**
 * 브라우저에서 서버를 부르는 유일한 창구입니다. 모든 요청은 같은 사이트의 BFF(/api/*)로 갑니다.
 * 실패 응답은 ApiError 하나로 바꿔 던지고, 모의 응답 모드에 따라 요청을 mock(src/mocks)으로 돌리기도 합니다.
 * mock으로 돌릴 경로는 `lib/mockMode.ts`가 정합니다.
 */
import { usesMock } from '@/lib/mockMode';
import type { components } from '@/types/api.gen';
import { resolveMock } from '@/mocks/handlers';

/** 브라우저는 같은 사이트의 BFF(`src/app/api/[...path]/route.ts`)만 부릅니다. 백엔드 주소는 서버만 압니다. */
export const API_BASE_URL = '/api';

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
export const networkError = (): ApiError =>
  new ApiError(ERROR_CODES.NETWORK_ERROR, NETWORK_MESSAGE, 0);

/** 실패 응답(`!res.ok`)을 공통 ApiError로 바꿉니다. 본문이 공통 형식이 아니면 INTERNAL_ERROR로 둡니다. */
export const toApiError = async (res: Response): Promise<ApiError> => {
  const requestId = res.headers.get('X-Request-ID');
  const body: unknown = await res.json().catch(() => null);
  if (isErrorResponse(body)) {
    return new ApiError(body.code, body.message, res.status, body.details ?? null, requestId);
  }
  return new ApiError(ERROR_CODES.INTERNAL_ERROR, FALLBACK_MESSAGE, res.status, null, requestId);
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

/** JSON 본문을 보내는 쓰기 요청(POST·PATCH·DELETE). */
export const apiSend = <T>(path: string, method: 'POST' | 'PATCH' | 'DELETE', body: unknown) =>
  apiFetch<T>(path, { method, body: JSON.stringify(body) });

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
