import type { ReactNode } from 'react';

import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useChatStream } from '@/features/chat/useChatStream';

import { buildMockSession } from '@/mocks/handlers';
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
    const session = { ...buildMockSession('lee'), session_id: 'acct-lee-2026-10-21' };

    const { result } = renderHook(() => useChatStream(session), { wrapper });

    await waitFor(() =>
      expect(result.current.messages.at(-1)?.text).toBe('대화 기록을 불러오지 못했어요.'),
    );
  });
});
