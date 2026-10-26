import { waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { pendingAskOf, useChatHistory } from '@/features/chat/useChatHistory';

import { sessionFor } from '@/test/fixtures';
import { renderWithProviders } from '@/test/renderWithProviders';

const message = (
  seq: number,
  role: string,
  text: string,
  payload: Record<string, unknown> | null = null,
) => ({
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
    const session = { ...sessionFor('lee'), session_id: 'acct-lee-2026-10-21' };
    let result: { current: ReturnType<typeof useChatHistory> } | undefined;
    const Probe = () => {
      result = { current: useChatHistory(session) };
      return null;
    };
    renderWithProviders(<Probe />);

    await waitFor(() => expect(result?.current.isSuccess).toBe(true));
    expect(result?.current.data).toEqual({
      messages: [
        { id: 'h-1', role: 'user', text: '오늘 면접 봤어요', inputKind: 'voice' },
        { id: 'h-2', role: 'assistant', text: '기록할게요.', cite: 'ACT-002' },
      ],
      pendingAsk: null,
    });
    expect(String(fetchSpy.mock.calls[0][0])).toContain('/accounts/lee/messages');
  });

  it('마지막 말풍선이 질문이면 그 선택지로 대기 질문을 되살린다', () => {
    const ask = {
      ...message(3, 'assistant', '희망 직종은 무엇인가요?', {
        choices: ['생산직', '창고·물류'],
        import_kind: null,
        accepts_file: false,
      }),
      kind: 'ask_user',
    };

    expect(pendingAskOf([message(1, 'user', '조립했어요'), ask])).toEqual({
      choices: ['생산직', '창고·물류'],
      import_kind: null,
      accepts_file: false,
    });
    expect(pendingAskOf([ask, message(4, 'user', '생산직')])).toBeNull();
  });
});
