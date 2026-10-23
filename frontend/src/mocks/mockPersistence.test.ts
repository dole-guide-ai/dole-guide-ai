import { afterEach, describe, expect, it } from 'vitest';

import { initChatState } from '@/features/chat/chatReducer';

import { getFormDrafts, replaceFormDraft, resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import { MOCK_ROUND_CHECKS } from '@/mocks/activities';
import { buildMockSession, resolveMock } from '@/mocks/handlers';
import {
  clearMockState,
  loadMockChat,
  restoreMockDrafts,
  saveMockChat,
  saveMockDrafts,
} from '@/mocks/mockPersistence';

describe('모의 화면 새로고침 복원 (F-03)', () => {
  afterEach(() => {
    clearMockState();
    resetForms();
    setSession(null);
  });

  it('같은 세션의 대화·선택지만 되돌리고, 다른 세션이나 지운 뒤에는 없다', () => {
    const session = buildMockSession('lee');
    const chat = {
      ...initChatState(session),
      messages: [{ id: 'm-1', role: 'user' as const, text: '오늘 면접 봤어요' }],
      choices: ['입사지원', '면접'],
      streamingId: 'm-2',
    };

    saveMockChat(session.session_id, chat);

    expect(loadMockChat(session.session_id)).toMatchObject({
      messages: chat.messages,
      choices: ['입사지원', '면접'],
      streamingId: null,
    });
    expect(loadMockChat('mock-other')).toBeNull();
    clearMockState();
    expect(loadMockChat(session.session_id)).toBeNull();
  });

  it('되살린 패널 B 값을 모의 회차 점검이 시드 대신 돌려준다', async () => {
    const session = buildMockSession('lee');
    setSession(session);
    const recorded = { ...MOCK_ROUND_CHECKS.lee, counted: 2, shortfall: 0, status: 'satisfied' };
    replaceFormDraft('activities', { values: recorded, fields: {} });
    saveMockDrafts(session.session_id);
    resetForms();

    expect(restoreMockDrafts(session.session_id)).toBe(true);
    expect(getFormDrafts().activities.values).toMatchObject({ counted: 2 });
    await expect(resolveMock('/procedure/current-round/check')).resolves.toMatchObject({
      counted: 2,
      status: 'satisfied',
    });
  });
});
