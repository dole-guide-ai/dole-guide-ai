import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiFetch } from '@/lib/api';
import { mockFetchJson } from '@/test/mockFetch';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('apiFetch', () => {
  it('성공하면 본문을 그대로 돌려준다', async () => {
    mockFetchJson({ status: 'ok' });

    await expect(apiFetch('/health')).resolves.toEqual({ status: 'ok' });
  });

  it('공통 에러 형식을 ApiError로 바꾼다', async () => {
    mockFetchJson(
      { code: 'NOT_FOUND', message: '찾는 정보가 없어요.', details: null },
      { status: 404 },
    );

    await expect(apiFetch('/items/1')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'NOT_FOUND',
      message: '찾는 정보가 없어요.',
      status: 404,
    });
  });

  it('형식이 다른 실패 응답은 INTERNAL_ERROR로 바꾼다', async () => {
    mockFetchJson({ detail: 'Bad Gateway' }, { status: 502 });

    await expect(apiFetch('/health')).rejects.toMatchObject({
      code: 'INTERNAL_ERROR',
      status: 502,
    });
  });

  it('네트워크 오류는 NETWORK_ERROR로 바꾼다', async () => {
    vi.spyOn(globalThis, 'fetch').mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await apiFetch('/health').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: 'NETWORK_ERROR', status: 0 });
  });
});
