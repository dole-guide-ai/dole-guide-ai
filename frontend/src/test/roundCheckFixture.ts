import type { components } from '@/types/api.gen';

type RoundCheck = components['schemas']['RoundCheck'];
type ActivityCheck = RoundCheck['activities'][number];

/** 합성 활동 한 건 (백엔드 `ActivityCheck` 모양). */
export const activityCheck = (overrides: Partial<ActivityCheck> = {}): ActivityCheck => ({
  activity_id: 'a1',
  activity_date: '2026-12-08',
  category: 'job_search',
  kind: 'job_application',
  route: 'work24',
  org_name: 'OO물류',
  source: 'import',
  planned: false,
  status: 'counted',
  required_evidence: [],
  has_evidence: false,
  rule_refs: ['ACT-001', 'ACT-132'],
  ...overrides,
});

/**
 * 이정호 4차 회차 점검 `GET /accounts/lee/rounds/current` 응답 (상세기획 2-2.6 계산 예, 기록 전).
 * 12.08 OO물류(고용24)는 인정, 같은 날 OO상사(홈페이지)는 같은 날이라 계산 제외 → 인정 1건 · 1건 더.
 */
export const LEE_ROUND_CHECK: RoundCheck = {
  round: 4,
  period_start: '2026-11-25',
  period_end: '2026-12-22',
  recognition_date: '2026-12-22',
  attendance_required: true,
  status: 'current',
  application_status: 'draft',
  d_day: 6,
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
    activityCheck(),
    activityCheck({
      activity_id: 'a2',
      route: 'company_site',
      org_name: 'OO상사',
      source: 'doc',
      status: 'same_day',
      required_evidence: ['채용공고', '지원 완료 화면 캡처(날짜가 보이게)'],
      rule_refs: ['ACT-001', 'ACT-136'],
    }),
  ],
  warnings: [
    {
      id: 'W1',
      message: '12월 8일 활동은 2건이지만 하루 1건만 인정돼요.',
      activity_ids: ['a1', 'a2'],
      rule_refs: ['ACT-055', 'ACT-110'],
    },
  ],
  limits_used: { lecture: 0, aptitude_test: 0, counseling: 0, volunteer: 0 },
  rule_review: 'not_verified',
  rule_refs: ['ACT-055', 'ACT-110', 'ACT-023'],
};

/** 12.16 OO물산 고용24 지원을 기록한 뒤의 점검 (충족, 인정 2건). */
export const LEE_ROUND_CHECK_SATISFIED: RoundCheck = {
  ...LEE_ROUND_CHECK,
  counted: 2,
  counted_job_search: 2,
  remaining: 0,
  check_status: 'satisfied',
  activities: [
    ...LEE_ROUND_CHECK.activities,
    activityCheck({ activity_id: 'a3', activity_date: '2026-12-16', org_name: 'OO물산' }),
  ],
};
