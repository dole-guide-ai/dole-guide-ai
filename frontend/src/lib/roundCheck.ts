/**
 * 백엔드 회차 점검(`RoundCheck`, GET …/rounds/current)을 패널 B가 쓰는 점검 모양(`RoundCheckRead`)으로 바꾸는
 * 임시 어댑터입니다. 패널 B가 아직 예전 점검 구조를 쓰고 있어서 둔 것이며, 화면을 새 API 타입으로 옮기면 지웁니다.
 * 활동별 상세·경고·인용은 회차 점검(F-18)이 응답에 넣으면 여기서 함께 옮깁니다.
 */

import type { components } from '@/types/api.gen';
import type { RoundCheckRead } from '@/types/procedure.types';

type RoundCheck = components['schemas']['RoundCheck'];

const DAY_MS = 86_400_000;

export const roundCheckFromServer = (check: RoundCheck, ruleGroup: string): RoundCheckRead => {
  const days =
    Math.round((Date.parse(check.period_end) - Date.parse(check.period_start)) / DAY_MS) + 1;
  const shortfall = Math.max(check.remaining, 0);
  return {
    round: check.round,
    rule_group: ruleGroup,
    period: { start: check.period_start, end: check.period_end, days },
    required: check.required,
    required_job_search: check.required_job_search,
    counted: check.counted,
    counted_job_search: 0,
    status: shortfall > 0 ? 'short' : 'satisfied',
    shortfall,
    shortfall_job_search: 0,
    activities: [],
    warnings: [],
    round_markers: Array.from({ length: check.round }, (_, index) => ({
      round: index + 1,
      state: index + 1 === check.round ? ('current' as const) : ('done' as const),
      is_attendance: index + 1 === check.round && check.attendance_required,
    })),
    rule_review: check.rule_review === 'verified' ? 'verified' : 'not_verified',
    cite: '',
    rule_refs: [],
  };
};
