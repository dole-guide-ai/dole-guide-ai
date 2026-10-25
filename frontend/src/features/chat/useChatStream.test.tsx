import type { ReactNode } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useChatStream } from '@/features/chat/useChatStream';

import { queryKeys } from '@/lib/queryKeys';
import { SSE_EVENTS } from '@/lib/sseEvents';
import { sessionFor } from '@/test/fixtures';
import { sseResponse } from '@/test/mockSse';
import { createTestQueryClient } from '@/test/renderWithProviders';

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
);

describe('useChatStream 새로고침 복원 (F-03)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('이전 대화를 못 받으면 서버 문구를 말풍선으로 알린다', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      Response.json(
        { code: 'INTERNAL_ERROR', message: '대화 기록을 불러오지 못했어요.' },
        { status: 500 },
      ),
    );
    const session = { ...sessionFor('lee'), session_id: 'acct-lee-2026-10-21' };

    const { result } = renderHook(() => useChatStream(session), { wrapper });

    await waitFor(() =>
      expect(result.current.messages.at(-1)?.text).toBe('대화 기록을 불러오지 못했어요.'),
    );
  });
});

describe('useChatStream 이력서 버전 맞추기', () => {
  afterEach(() => vi.restoreAllMocks());

  it('대화가 이력서를 고친 턴이 끝나면 이력서를 다시 받는다', async () => {
    const session = { ...sessionFor('park'), session_id: 'acct-park-2026-10-21' };
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
      String(input).includes('/messages') && !String(input).includes('?')
        ? sseResponse([
            {
              event: SSE_EVENTS.FORM_UPDATE,
              data: {
                form: 'resume',
                path: '/careers/c1/company_name',
                op: 'add',
                value: '한빛물류',
              },
            },
            { event: SSE_EVENTS.DONE, data: {} },
          ])
        : Response.json({ items: [], total: 0, next_cursor: null }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    const withClient = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useChatStream(session), { wrapper: withClient });
    await act(() => result.current.send('한빛물류에서 일했어요'));

    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.resumeForm(session.session_id) });
  });
});
