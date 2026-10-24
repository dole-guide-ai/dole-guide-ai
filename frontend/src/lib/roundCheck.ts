/**
 * 백엔드 회차 점검(`RoundCheck`, GET …/rounds/current)을 패널 B가 쓰는 점검 모양(`RoundCheckRead`)으로 바꾸는
 * 어댑터입니다. 패널 B는 상세기획 2-2.2 이름(category = 활동 종류, kind = 구직/구직 외)을 쓰고, 백엔드는 API 설계
 * 이름(category = 구직/구직 외, kind = 활동 종류)을 씁니다. 패널 B를 api.gen 타입으로 옮기면 지웁니다.
 */

import type { components } from '@/types/api.gen';
import type { ActivitySource, RoundActivity, RoundCheckRead } from '@/types/procedure.types';

type RoundCheck = components['schemas']['RoundCheck'];
type ActivityCheck = RoundCheck['activities'][number];

/** 활동을 넣거나 빼면 백엔드가 다시 계산한 회차 점검을 이 경로로 보냅니다 (`form: "activities"`). */
export const ROUND_CHECK_PATH = '/round_check';

const JOB_SEARCH = 'job_search';
// 증빙 파일 이름은 응답에 없어 첨부 여부만 표시합니다.
const ATTACHED_LABEL = '증빙 파일';

const toActivity = (round: number, activity: ActivityCheck): RoundActivity => ({
  item_id: activity.activity_id,
  round,
  date: activity.activity_date,
  category: activity.kind,
  kind: activity.category === JOB_SEARCH ? 'job_search' : 'other',
  route: (activity.route ?? 'center') as RoundActivity['route'],
  org_name: activity.org_name ?? '',
  job_title: activity.job_title,
  evidence: {
    required: activity.required_evidence ?? [],
    attached: activity.has_evidence ? [ATTACHED_LABEL] : [],
  },
  source: (activity.source ?? 'user_answer') as ActivitySource,
  status: activity.status,
  rule_refs: activity.rule_refs,
});

export const roundCheckFromServer = (check: RoundCheck, ruleGroup?: string): RoundCheckRead => ({
  round: check.round,
  rule_group: ruleGroup ?? check.rule_group,
  period: { start: check.period_start, end: check.period_end, days: check.period_days },
  required: check.required,
  required_job_search: check.required_job_search,
  counted: check.counted,
  counted_job_search: check.counted_job_search,
  status: check.check_status,
  shortfall: check.remaining,
  shortfall_job_search: check.remaining_job_search,
  activities: check.activities.map((activity) => toActivity(check.round, activity)),
  warnings: check.warnings.map((warning) => ({
    id: warning.id,
    message: warning.message,
    item_ids: warning.activity_ids,
  })),
  round_markers: Array.from({ length: check.round }, (_, index) => ({
    round: index + 1,
    state: index + 1 === check.round ? ('current' as const) : ('done' as const),
    is_attendance: index + 1 === check.round && check.attendance_required,
  })),
  rule_review: check.rule_review,
  cite: '',
  rule_refs: check.rule_refs,
});
