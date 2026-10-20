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

  it('고용24에서 불러올게요는 입사지원 목록을 열고, 고른 OO물산은 활동으로 기록된다 (2-2.5)', () => {
    const open = buildMockChatEvents('lee', '고용24에서 불러올게요', []);
    const recorded = buildMockChatEvents(
      'lee',
      '고용24에서 고른 1건 넣어 주세요',
      [],
      [],
      ['wa_003'],
    );

    expect(open.at(-1)).toMatchObject({
      event: 'ask_user',
      data: { import_kind: 'work24-activities' },
    });
    expect(updates(recorded)).toContainEqual(
      expect.objectContaining({ form: 'activities', path: 'activities', op: 'append' }),
    );
  });
});

describe('박진수 통합경력증명 불러오기', () => {
  it('고른 경력·직업훈련만 넣고, 직급을 이어서 묻는다 (2-1.5)', () => {
    const events = buildMockChatEvents(
      'park',
      '고용24에서 고른 2건 넣어 주세요',
      [],
      [],
      ['cc_career_001', 'cc_training_001'],
    );
    const paths = updates(events).map((update) => update.path);

    expect(paths).toContain('competencies.careers');
    expect(paths).toContain('competencies.vocational_training');
    expect(paths).not.toContain('competencies.certifications');
    expect(updates(events).find((u) => u.path.endsWith('company_name'))).toMatchObject({
      source: 'work24_import',
    });
    expect(events.at(-1)).toMatchObject({
      event: 'ask_user',
      data: { choices: ['말로 할게요', '없었어요'] },
    });
  });
});
