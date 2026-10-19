import { resolveMock } from '@/mocks/handlers';

import { ApiError } from './apiError';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/** 백엔드 없이 화면을 볼 때 `NEXT_PUBLIC_USE_MOCK=1`로 켭니다. 응답은 `src/mocks/`의 스냅샷입니다. */
export const IS_MOCK_API = process.env.NEXT_PUBLIC_USE_MOCK === '1';

export const apiFetch = async <T>(path: string, init?: RequestInit): Promise<T> => {
  if (IS_MOCK_API) return resolveMock<T>(path, init);

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!res.ok) throw new ApiError(res.status, path);
  return res.json() as Promise<T>;
};
