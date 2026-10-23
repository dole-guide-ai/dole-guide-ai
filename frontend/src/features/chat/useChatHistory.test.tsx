import { waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useChatHistory } from '@/features/chat/useChatHistory';

import { buildMockSession } from '@/mocks/handlers';
import { renderWithProviders } from '@/test/renderWithProviders';

const message = (seq: number, role: string, text: string, payload: object | null = null) => ({
  seq,
  role,
  kind: 'text',
  text,
  payload,
  created_at: '2026-10-21T10:00:00+09:00',
});

describe('useChatHistory (F-03)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('실제 서버 세션은 저장된 대화를 이어 받아 말풍선으로 바꾼다', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
      String(input).includes('cursor=1')
        ? Response.json({
            items: [message(2, 'assistant', '기록할게요.', { cite: 'ACT-002' })],
            total: 2,
            next_cursor: null,
          })
        : Response.json({
            items: [message(1, 'user', '오늘 면접 봤어요', { input_kind: 'voice' })],
            total: 2,
            next_cursor: 1,
          }),
    );
    const session = { ...buildMockSession('lee'), session_id: 'acct-lee-2026-10-21' };
    let result: { current: ReturnType<typeof useChatHistory> } | undefined;
    const Probe = () => {
      result = { current: useChatHistory(session) };
      return null;
    };
    renderWithProviders(<Probe />);

    await waitFor(() => expect(result?.current.isSuccess).toBe(true));
    expect(result?.current.data).toEqual([
      { id: 'h-1', role: 'user', text: '오늘 면접 봤어요', inputKind: 'voice' },
      { id: 'h-2', role: 'assistant', text: '기록할게요.', cite: 'ACT-002' },
    ]);
    expect(String(fetchSpy.mock.calls[0][0])).toContain('/accounts/lee/messages');
  });

  it('모의 세션은 대화 기록을 받지 않는다', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const Probe = () => {
      useChatHistory(buildMockSession('lee'));
      return null;
    };
    renderWithProviders(<Probe />);

    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
