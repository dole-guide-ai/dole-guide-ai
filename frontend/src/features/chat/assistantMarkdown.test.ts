import { describe, expect, it } from 'vitest';

import { trimOpenEmphasis } from '@/features/chat/assistantMarkdown';

describe('trimOpenEmphasis', () => {
  it('닫히지 않은 마지막 **만 뺀다', () => {
    expect(trimOpenEmphasis('실업급여는 **구직등')).toBe('실업급여는 구직등');
  });

  it('닫힌 강조는 그대로 둔다', () => {
    expect(trimOpenEmphasis('**3건**을 더 해야 해요')).toBe('**3건**을 더 해야 해요');
  });
});
