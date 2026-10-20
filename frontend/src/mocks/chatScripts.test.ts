import { describe, expect, it } from 'vitest';

import { OPEN_FORM_MESSAGE } from '@/features/procedure/activityLabels';

import type { FormUpdateEvent, SseMessage } from '@/types/chat.types';
import { buildMockChatEvents } from '@/mocks/chatScripts';

const updates = (events: SseMessage[]): FormUpdateEvent[] =>
  events.flatMap((event) => (event.event === 'form_update' ? [event.data] : []));

describe('이정호 신청서 모의 대화', () => {
  it('신청서 만들기는 패널을 C로 바꾸고 근로·소득 질문부터 한다 (2-3.3)', () => {
    const events = buildMockChatEvents('lee', OPEN_FORM_MESSAGE, []);

    expect(updates(events)).toContainEqual(
      expect.objectContaining({ form: 'procedure', path: 'entry.panel', value: 'C' }),
    );
    expect(events.at(-1)).toMatchObject({
      event: 'ask_user',
      data: { choices: ['없어요', '있어요', '잘 모르겠어요'] },
    });
  });

  it('다음 실업인정일을 알려 주면 5차로 넘어간다 (평가 form-005)', () => {
    const events = buildMockChatEvents('lee', '다음은 1월 19일이래요', []);
    const byPath = Object.fromEntries(updates(events).map((update) => [update.path, update.value]));

    expect(byPath.state).toMatchObject({
      completed_rounds: 4,
      next_recognition_date: '2027-01-19',
      demo_today: '2026-12-22',
    });
    expect(byPath.derived).toMatchObject({ current_round: 5, d_day: 28 });
    expect(byPath['entry.panel']).toBe('B');
  });
});
