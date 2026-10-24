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
  rule_group: 'general',
  period_days: 28,
  required: 2,
  required_job_search: 1,
  counted: 1,
  counted_job_search: 1,
  remaining: 1,
  remaining_job_search: 0,
  check_status: 'short',
  weeks: [],
  activities: [
    {
      activity_id: 'a2',
      activity_date: '2026-12-08',
      category: 'job_search',
      kind: 'job_application',
      route: 'company_site',
      org_name: 'OO상사',
      source: 'doc',
      planned: false,
      status: 'same_day',
      required_evidence: ['채용공고'],
      has_evidence: false,
      rule_refs: ['ACT-136'],
    },
  ],
  warnings: [{ id: 'W1', message: '하루 1건만 인정돼요.', activity_ids: ['a2'], rule_refs: [] }],
  limits_used: { lecture: 0, aptitude_test: 0, counseling: 0, volunteer: 0 },
  rule_review: 'not_verified',
  rule_refs: ['ACT-055'],
  ...overrides,
});

describe('roundCheckFromServer (F-18)', () => {
  it('점검 결과를 패널 B 모양으로 옮긴다', () => {
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
      rule_refs: ['ACT-055'],
    });
    expect(result.activities[0]).toMatchObject({
      item_id: 'a2',
      category: 'job_application',
      kind: 'job_search',
      source: 'doc',
      status: 'same_day',
      evidence: { required: ['채용공고'], attached: [] },
    });
    expect(result.warnings).toEqual([
      { id: 'W1', message: '하루 1건만 인정돼요.', item_ids: ['a2'] },
    ]);
    expect(result.round_markers.at(-1)).toEqual({
      round: 4,
      state: 'current',
      is_attendance: true,
    });
    expect(result.round_markers[0].state).toBe('done');
  });

  it('남은 건수가 없으면 충족이다', () => {
    expect(
      roundCheckFromServer(
        check({ counted: 2, remaining: 0, check_status: 'satisfied' }),
        'general',
      ),
    ).toMatchObject({
      status: 'satisfied',
      shortfall: 0,
    });
  });
});
