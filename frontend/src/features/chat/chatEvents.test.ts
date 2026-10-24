import { describe, expect, it } from 'vitest';

import { CHAT_ACTIONS } from '@/features/chat/chatActions';
import { activeToolAfter, chatActionFor, isBubbleEvent } from '@/features/chat/chatEvents';

import { SSE_EVENTS } from '@/lib/sseEvents';
import { TOOL_STATUS } from '@/types/chat.types';

describe('chatEvents', () => {
  it('말풍선 이벤트만 리듀서 액션으로 바꾼다', () => {
    const token = { event: SSE_EVENTS.TOKEN, data: { text: '안녕' } } as const;
    const tool = {
      event: SSE_EVENTS.TOOL_CALL,
      data: { name: 'check_round', status: TOOL_STATUS.STARTED },
    } as const;

    expect(isBubbleEvent(token)).toBe(true);
    expect(isBubbleEvent(tool)).toBe(false);
    expect(chatActionFor(token)).toEqual({ type: CHAT_ACTIONS.TOKEN, text: '안녕' });
  });

  it('도구가 시작하면 이름을, 끝나면 null을 돌려준다', () => {
    expect(activeToolAfter({ name: 'check_round', status: TOOL_STATUS.STARTED })).toBe(
      'check_round',
    );
    expect(activeToolAfter({ name: 'check_round', status: TOOL_STATUS.FINISHED })).toBeNull();
  });
});
