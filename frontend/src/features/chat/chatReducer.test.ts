import { describe, expect, it } from 'vitest';

import { chatReducer, initChatState } from '@/features/chat/chatReducer';

import { buildMockSession } from '@/mocks/handlers';

const run = (actions: Parameters<typeof chatReducer>[1][]) =>
  actions.reduce(chatReducer, initChatState(buildMockSession('lee')));

describe('chatReducer', () => {
  it('첫 안내 말풍선과 선택지로 시작한다', () => {
    const state = initChatState(buildMockSession('lee'));
    expect(state.messages).toHaveLength(2);
    expect(state.choices).toHaveLength(3);
  });

  it('token은 한 말풍선에 이어 붙고 done에서 근거 줄이 붙는다', () => {
    const state = run([
      { type: 'user_sent', text: '추천해 주세요', inputKind: 'choice' },
      { type: 'token', text: '지금 인정되는 ' },
      { type: 'token', text: '활동은 1건이에요.' },
      { type: 'done', cite: '안내문' },
    ]);

    const last = state.messages[state.messages.length - 1];
    expect(state.choices).toEqual([]);
    expect(last).toMatchObject({
      role: 'assistant',
      text: '지금 인정되는 활동은 1건이에요.',
      cite: '안내문',
    });
    expect(state.streamingId).toBeNull();
  });

  it('ask_user는 질문 말풍선을 만들고 선택지를 바꾼다', () => {
    const state = run([
      { type: 'user_sent', text: '새 활동 기록할게요', inputKind: 'choice' },
      { type: 'ask_user', text: '언제 하셨어요?', choices: ['오늘', '어제', '다른 날'] },
      { type: 'done' },
    ]);

    expect(state.messages[state.messages.length - 1].text).toBe('언제 하셨어요?');
    expect(state.choices).toEqual(['오늘', '어제', '다른 날']);
  });

  it('system 메시지는 스트리밍 중이던 빈 말풍선을 정리하고 오류를 보여 준다', () => {
    const state = run([
      { type: 'user_sent', text: '안녕', inputKind: 'text' },
      { type: 'token', text: '' },
      { type: 'system', text: '지금 답을 만들기 어려워요.' },
    ]);

    expect(state.messages.map((m) => m.role)).toEqual(['assistant', 'assistant', 'user', 'system']);
  });

  it('restore는 저장된 대화로 말풍선을 바꾸되, 이미 이어 간 대화는 덮지 않는다 (F-03)', () => {
    const saved = [
      { id: 'h-1', role: 'user' as const, text: '오늘 면접 봤어요' },
      { id: 'h-2', role: 'assistant' as const, text: '어떤 활동이었어요?' },
    ];

    const answered = run([{ type: 'restore', messages: saved, pendingAsk: null }]);
    expect(answered.messages).toEqual(saved);
    // 답을 마친 대화면 진입 선택지를 지웁니다
    expect(answered.choices).toEqual([]);
    const waiting = run([
      {
        type: 'restore',
        messages: saved,
        pendingAsk: {
          choices: ['고를게요'],
          import_kind: 'work24-activities',
          accepts_file: true,
        },
      },
    ]);
    expect(waiting.choices).toEqual(['고를게요']);
    expect(waiting.importKind).toBe('work24-activities');
    expect(waiting.acceptsFile).toBe(true);
    expect(answered.acceptsFile).toBe(false);
    const continued = run([
      { type: 'user_sent', text: '추천해 주세요', inputKind: 'choice' },
      { type: 'restore', messages: saved, pendingAsk: null },
    ]);
    expect(continued.messages.at(-1)?.text).toBe('추천해 주세요');
  });
});
