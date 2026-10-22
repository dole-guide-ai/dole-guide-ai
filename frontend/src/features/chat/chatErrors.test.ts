import { describe, expect, it } from 'vitest';

import { describeChatError } from '@/features/chat/chatErrors';

describe('describeChatError', () => {
  it.each(['LLM_UNAVAILABLE', 'RATE_LIMITED', 'TIMEOUT', 'TURN_IN_PROGRESS', 'NETWORK_ERROR'])(
    '%s는 보낸 글을 되돌린다',
    (code) => {
      expect(describeChatError({ code }).restoresInput).toBe(true);
    },
  );

  it('그 밖의 오류는 패널 값을 바꾸지 않았다고 알린다', () => {
    expect(describeChatError({ code: 'INTERNAL_ERROR' })).toEqual({
      text: '처리 중 문제가 생겼어요. 패널 값은 바꾸지 않았어요.',
      restoresInput: false,
    });
  });
});
