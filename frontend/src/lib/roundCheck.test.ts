import { describe, expect, it } from 'vitest';

import { roundCheckFromServer } from '@/lib/roundCheck';
import type { components } from '@/types/api.gen';

type RoundCheck = components['schemas']['RoundCheck'];

const check = (overrides: Partial<RoundCheck> = {}): RoundCheck => ({
  round: 4,
  period_start: '2026-11-25',
  period_end: '2026-12-22',
  recognition_date: '2026-12-22',
  attendance_required: true,
  status: 'current',
  application_status: 'draft',
  d_day: 3,
  required: 2,
  required_job_search: 1,
  counted: 1,
  remaining: 1,
  activities: [],
  required_evidence: [],
  limits_used: { lecture: 0, aptitude_test: 0, counseling: 0, volunteer: 0 },
  rule_review: 'not_verified',
  ...overrides,
});

describe('roundCheckFromServer (F-22)', () => {
  it('남은 건수를 부족 건수로, 회차 기간을 일수로 옮긴다', () => {
    const result = roundCheckFromServer(check(), 'general');

    expect(result).toMatchObject({
      round: 4,
      rule_group: 'general',
      period: { start: '2026-11-25', end: '2026-12-22', days: 28 },
      required: 2,
      counted: 1,
      status: 'short',
      shortfall: 1,
      rule_review: 'not_verified',
    });
    expect(result.round_markers.at(-1)).toEqual({
      round: 4,
      state: 'current',
      is_attendance: true,
    });
    expect(result.round_markers[0].state).toBe('done');
  });

  it('남은 건수가 없으면 충족이다', () => {
    expect(roundCheckFromServer(check({ counted: 2, remaining: 0 }), 'general')).toMatchObject({
      status: 'satisfied',
      shortfall: 0,
    });
  });
});
