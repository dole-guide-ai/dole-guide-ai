import type { FormUpdateEvent } from '@/types/chat.types';
import type {
  RecommendationsRead,
  RoundActivity,
  RoundCheckRead,
  RoundMarker,
} from '@/types/procedure.types';

/**
 * 패널 B 모의 스냅샷 (상세기획 2-2.6 이정호 계산 예 · 2-2.8 추천 결과 · 2-2.12 `check_round` 예시).
 * 같은 날 대표 고르기·인정 건수 같은 계산은 백엔드 `check_round`가 맡고, 여기서는 결과만 둡니다.
 */
const SOURCE_2026_NOTICE = '실업인정 인정기준 안내문(2026.3.1~ 신청자) · 취업드림수첩 2025';

const LEE_MARKERS: RoundMarker[] = [
  { round: 1, state: 'done', is_attendance: true },
  { round: 2, state: 'done', is_attendance: false },
  { round: 3, state: 'done', is_attendance: false },
  { round: 4, state: 'current', is_attendance: true },
];

/** 기록 전 (1.9 seed): 12.08 두 건이 같은 날이라 대표 OO물류만 인정. */
const LEE_ACTIVITIES: RoundActivity[] = [
  {
    item_id: 'a1',
    round: 4,
    date: '2026-12-08',
    category: '입사지원',
    kind: 'job_search',
    route: 'work24',
    org_name: 'OO물류',
    job_title: '일반 사무',
    evidence: { required: [], attached: [] },
    source: 'work24_import',
    status: 'counted',
    rule_refs: ['ACT-001', 'ACT-132'],
  },
  {
    item_id: 'a2',
    round: 4,
    date: '2026-12-08',
    category: '입사지원',
    kind: 'job_search',
    route: 'company_site',
    org_name: 'OO상사',
    job_title: null,
    evidence: {
      required: ['채용공고', '지원 완료 화면 캡처'],
      attached: ['지원완료_캡처.png'],
    },
    source: 'document',
    status: 'same_day',
    rule_refs: ['ACT-055', 'ACT-110', 'ACT-136'],
  },
];

const lee: RoundCheckRead = {
  round: 4,
  rule_group: 'general',
  period: { start: '2026-11-25', end: '2026-12-22', days: 28 },
  required: 2,
  required_job_search: 1,
  counted: 1,
  counted_job_search: 1,
  status: 'short',
  shortfall: 1,
  shortfall_job_search: 0,
  activities: LEE_ACTIVITIES,
  warnings: [
    {
      id: 'W1',
      message: '12월 8일 활동은 2건이지만 하루 1건만 인정돼요.',
      item_ids: ['a1', 'a2'],
    },
  ],
  round_markers: LEE_MARKERS,
  rule_review: 'not_verified',
  cite: SOURCE_2026_NOTICE,
  rule_refs: ['ACT-025', 'ACT-026', 'ACT-055', 'ACT-110', 'DUE-044', 'DUE-090'],
  recommendations_open: false,
};

export const MOCK_ROUND_CHECKS: Record<string, RoundCheckRead> = { lee };

/**
 * 4차 출석 준비 확인 뒤 "다음은 1월 19일이래요"로 넘어간 5차 첫 화면 (2-3.7, 평가 form-005).
 * 5차 `general` = 4주 2건 · 구직활동 1건 포함, 온라인 회차, 대상 기간 12.23 ~ 01.19.
 */
const lee5: RoundCheckRead = {
  ...lee,
  round: 5,
  period: { start: '2026-12-23', end: '2027-01-19', days: 28 },
  counted: 0,
  counted_job_search: 0,
  shortfall: 2,
  shortfall_job_search: 1,
  activities: [],
  warnings: [],
  round_markers: [
    ...LEE_MARKERS.map((marker) => ({ ...marker, state: 'done' as const })),
    { round: 5, state: 'current', is_attendance: false },
  ],
  rule_refs: ['ACT-027', 'ACT-028', 'DUE-044', 'DUE-090'],
  recommendations_open: false,
};

/** 회차가 넘어간 뒤의 점검 결과 (계정 → 회차 → 결과). */
export const MOCK_NEXT_ROUND_CHECKS: Record<string, Record<number, RoundCheckRead>> = {
  lee: { 5: lee5 },
};

export const MOCK_RECOMMENDATIONS: Record<string, RecommendationsRead> = {
  lee: {
    items: [
      {
        recommendation_id: 'rec_work24_apply',
        title: '입사지원 (고용24)',
        detail: "희망 직종 '일반 사무' 공고에 고용24로 지원",
        kind: 'job_search',
        evidence_label: '증빙 불필요',
        limit_text: null,
        rule_refs: ['ACT-001', 'ACT-132'],
      },
      {
        recommendation_id: 'rec_step_online',
        title: '온라인 취업특강 (STEP)',
        detail: '1과정을 끝까지 수강 (진도율 100%)',
        kind: 'other',
        evidence_label: '증빙 불필요',
        limit_text: '한도 2회 중 0회 사용',
        rule_refs: ['ACT-043', 'ACT-117'],
      },
      {
        recommendation_id: 'rec_interview',
        title: '면접',
        detail: '잡힌 면접이 있으면',
        kind: 'job_search',
        evidence_label: '면접확인서 + 명함',
        limit_text: null,
        rule_refs: ['ACT-002', 'ACT-137'],
      },
    ],
    deadline_text: '12월 8일이 아닌 다른 날, 인정일 전날 12월 21일(월)까지 하시길 권해요.',
    note: '공고는 고용24 채용정보에서 직접 골라 주세요.',
    cite: SOURCE_2026_NOTICE,
  },
};

/** 추천의 `선택`을 누르면 예정 활동(`planned`)으로 들어가는 값 (2-2.8). 날짜는 권장 기한 전 빈 날. */
export const MOCK_PLANNED_ACTIVITIES: Record<string, Omit<RoundActivity, 'item_id'>> = {
  rec_work24_apply: {
    round: 4,
    date: '2026-12-18',
    category: '입사지원',
    kind: 'job_search',
    route: 'work24',
    org_name: '(공고 선택 전)',
    evidence: { required: [], attached: [] },
    source: 'conversation',
    status: 'planned',
  },
  rec_step_online: {
    round: 4,
    date: '2026-12-18',
    category: '온라인 취업특강',
    kind: 'other',
    route: 'step_online',
    org_name: '고용24 온라인 취업특강',
    evidence: { required: [], attached: [] },
    source: 'conversation',
    status: 'planned',
  },
  rec_interview: {
    round: 4,
    date: '2026-12-18',
    category: '면접',
    kind: 'job_search',
    route: 'interview',
    org_name: '(면접 회사)',
    evidence: { required: ['면접확인서', '명함'], attached: [] },
    source: 'conversation',
    status: 'planned',
  },
};

const set = (path: string, value: unknown): FormUpdateEvent => ({
  form: 'activities',
  path,
  op: 'set',
  value,
});

/**
 * 활동 빼기 (2-2.11 "활동을 빼 달라고 함" → 삭제 후 다시 계산)의 모의 결과. 백엔드가 `check_round`를
 * 다시 계산해 돌려줄 값을 이정호 활동별로 적어 둡니다. 표에 없는 활동(예정 등)은 목록에서만 뺍니다.
 */
export const MOCK_ACTIVITY_REMOVALS: Record<string, FormUpdateEvent[]> = {
  // 같은 날 대표였던 OO물류를 빼면 OO상사가 대표가 되어 인정 건수는 그대로예요.
  a1: [set('activities.a2.status', 'counted'), set('warnings', [])],
  a2: [set('warnings', [])],
  a3: [
    set('counted', 1),
    set('counted_job_search', 1),
    set('shortfall', 1),
    set('status', 'short'),
  ],
};
