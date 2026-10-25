import { describe, expect, it } from 'vitest';

import { nextStepView } from '@/lib/nextStep';
import { sessionFor } from '@/test/fixtures';

describe('nextStepView', () => {
  it('실업인정 단계는 회차·인정일·D-day·출석 안내로 나눈다', () => {
    const session = sessionFor('lee');

    expect(nextStepView(session)).toEqual({
      label: '다음 기한',
      text: '4차 실업인정일 10월 27일(화)',
      dday: 'D-6',
      note: '고용센터에 직접 가요',
    });
  });

  it('출석 회차가 아니면 덧붙임이 없고, 오늘이면 D-day로 쓴다', () => {
    const session = sessionFor('lee');
    session.derived = { ...session.derived, is_attendance_round: false, d_day: 0 };

    expect(nextStepView(session)).toMatchObject({ dday: 'D-day', note: undefined });
  });

  it('그 밖의 단계는 백엔드 문구에서 머리말만 뗀다', () => {
    expect(nextStepView(sessionFor('park'))).toEqual({
      label: '다음 할 일',
      text: '이력서 저장 후 온라인 교육(약 1시간)',
    });
  });

  it('보여 줄 문구가 없으면 null', () => {
    const session = sessionFor('park');
    session.entry = { ...session.entry, next_step_text: '' };

    expect(nextStepView(session)).toBeNull();
  });
});
