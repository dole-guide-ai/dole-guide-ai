import type { ReactNode } from 'react';

import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useResetAccount } from '@/features/dashboard/useResetAccount';

import { getSession, setSession } from '@/lib/sessionStore';
import { sessionFor } from '@/test/fixtures';
import { createTestQueryClient } from '@/test/renderWithProviders';

const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
);

const error = (status: number) =>
  Response.json({ code: 'INTERNAL_ERROR', message: '문제가 생겼어요.', details: null }, { status });

/** DELETE·PUT 응답을 메서드별로 정합니다. */
const mockReset = (deleteResponse: Response, putResponse: Response) =>
  vi
    .spyOn(globalThis, 'fetch')
    .mockImplementation(async (_input, init) =>
      init?.method === 'DELETE' ? deleteResponse : putResponse,
    );

describe('useResetAccount', () => {
  beforeEach(() => {
    setSession(sessionFor('park'));
    vi.spyOn(window, 'alert').mockImplementation(() => {});
  });

  afterEach(() => {
    setSession(null);
    push.mockClear();
  });

  it('DELETE가 실패하면 계정이 그대로라 세션을 지키고 다시 눌러 달라고 안내한다', async () => {
    mockReset(error(500), error(500));

    const { result } = renderHook(() => useResetAccount('park'), { wrapper });
    result.current.mutate();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(window.alert).toHaveBeenCalledWith('초기화하지 못했어요. 잠시 후 다시 눌러 주세요.');
    expect(getSession()?.persona_id).toBe('park');
    expect(push).not.toHaveBeenCalled();
  });

  it('DELETE 뒤 PUT이 실패하면 세션을 비우고 첫 화면으로 보낸다', async () => {
    mockReset(new Response(null, { status: 204 }), error(500));

    const { result } = renderHook(() => useResetAccount('park'), { wrapper });
    result.current.mutate();

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(window.alert).toHaveBeenCalledWith(
      '초기화 중 문제가 생겨 계정을 다시 만들지 못했어요. 첫 화면에서 계정을 다시 골라 주세요.',
    );
    expect(getSession()).toBeNull();
    expect(push).toHaveBeenCalledWith('/');
  });
});
