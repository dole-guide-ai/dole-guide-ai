import type { components } from '@/types/api.gen';
import { resolveMock } from '@/mocks/handlers';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/** 백엔드 없이 화면을 볼 때 `NEXT_PUBLIC_USE_MOCK=1`로 켭니다. 응답은 `src/mocks/`의 스냅샷입니다. */
export const IS_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK === '1';

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

const toApiError = async (res: Response): Promise<ApiError> => {
  const requestId = res.headers.get('X-Request-ID');
  const body: unknown = await res.json().catch(() => null);
  if (isErrorResponse(body)) {
    return new ApiError(body.code, body.message, res.status, body.details ?? null, requestId);
  }
  return new ApiError('INTERNAL_ERROR', FALLBACK_MESSAGE, res.status, null, requestId);
};

export const apiFetch = async <T>(path: string, init?: RequestInit): Promise<T> => {
  if (IS_MOCK_API) return resolveMock<T>(path, init);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError('NETWORK_ERROR', NETWORK_MESSAGE, 0);
  }
  if (!res.ok) throw await toApiError(res);
  return res.json() as Promise<T>;
};
