import { formatShortDate } from '@/lib/dateFormat';
import { citeOf } from '@/lib/sources';
import type { ActivityStatus, RoundActivity } from '@/types/procedure.types';
import type {
  ExcludedActivity,
  JobSearchActivity,
  OtherActivity,
  RecognitionFormRead,
  ReemploymentActivity,
} from '@/types/recognition.types';

/**
 * 실업인정 신청서 모의 스냅샷 (상세기획 2-3.10, 시안 2-3-1 시점). 이정호 4차, 출석 회차, 기준일 12.16 10:00.
 * 본인 답변(근로·취업·산재)과 다음 출석일까지 활동은 비어 있고, 실업크레딧·통지방법은 3차(11.24) 답이 남아 있습니다.
 * 제출 버튼 상태·제출 가능 여부는 백엔드 `submit_mode`·`can_submit` 결과를 흉내 낸 값입니다.
 */
const SOURCE_FORM = citeOf('SRC-001', 'SRC-016');

const SELF = { status: 'confirmed', source: 'self_answer' } as const;
const WORK24 = { status: 'extracted', source: 'work24_import' } as const;
const PREV_ANSWER = {
  ...SELF,
  evidence: { kind: 'previous_round', date: '2026-11-24', note: '3차 신청 때 고른 값' },
};

const lee: RecognitionFormRead = {
  schema_version: 'work24_recognition_v1',
  recognition_round: 4,
  status: 'review',
  recognition_info: {
    recognition_date: '2026-12-22',
    period_start: '2026-11-25',
    period_end: '2026-12-22',
    attendance_round: true,
  },
  unemployment_credit: {
    is_applicable: true,
    credit_application_choice: '희망함',
    notice_delivery_method: '전자고지',
    automatic_payment_choice: '희망하지 않음',
    income_asset_consent: '동의함',
    answered_on: '2026-11-24',
  },
  work_and_employment: {
    has_work_or_service: null,
    has_employment: null,
    has_industrial_accident_benefit_right: null,
    answered_on: null,
  },
  reemployment_activity: {
    required: { activities: 2, job_search: 1 },
    counted: { activities: 2, job_search: 2 },
    has_job_search_activity: true,
    job_search_activities: [
      {
        item_id: 'job_activity_001',
        activity_date: '2026-12-08',
        company_name: 'OO물류',
        recruitment_contact: '인사팀',
        recruitment_occupation: '일반 사무',
        salary_level: null,
        job_search_method: '고용24(워크넷)',
        application_method: '고용24(워크넷)',
        activity_result: '서류전형 심사진행 중',
        attachment_ids: [],
        source: 'work24_import',
      },
      {
        item_id: 'job_activity_003',
        activity_date: '2026-12-16',
        company_name: 'OO물산',
        recruitment_contact: '총무팀',
        recruitment_occupation: '사무보조',
        salary_level: null,
        job_search_method: '고용24(워크넷)',
        application_method: '고용24(워크넷)',
        activity_result: '서류전형 심사진행 중',
        attachment_ids: [],
        source: 'work24_import',
      },
    ],
    excluded: [
      {
        item_id: 'job_activity_002',
        reason: 'same_day',
        activity_date: '2026-12-08',
        company_name: 'OO상사',
      },
    ],
    has_other_reemployment_activity: false,
    other_reemployment_activities: [],
  },
  notification_and_plan: {
    payment_notification_method: '휴대전화 문자메시지',
    desired_reemployment_type: ['상용근로자'],
    next_activity: { value: null, memo: null, answered_on: null },
  },
  personal_information_consent: { value: null, answered_on: null },
  checklist: [
    { key: 'self_answers', done: false, blocking: true },
    { key: 'job_search_fields', done: true, blocking: true },
    { key: 'notification', done: true, blocking: true },
    { key: 'next_activity', done: false, blocking: true },
    { key: 'unemployment_credit', done: true, blocking: false },
    { key: 'requirement_met', done: true, blocking: false },
    { key: 'evidence_ok', done: true, blocking: false },
  ],
  attend_items: ['id_card', 'eligibility_card'],
  submit_mode: 'attend',
  can_submit: false,
  locked_reason: null,
  mock_submission: null,
  field_states: {
    recognition_info: { status: 'confirmed', source: 'computed' },
    unemployment_credit: PREV_ANSWER,
    'reemployment_activity.job_search_activities.job_activity_001': WORK24,
    'reemployment_activity.job_search_activities.job_activity_003': WORK24,
    'notification_and_plan.payment_notification_method': PREV_ANSWER,
    'notification_and_plan.desired_reemployment_type': PREV_ANSWER,
  },
  cite: SOURCE_FORM,
  rule_refs: ['DUE-044', 'DUE-090', 'DUE-102', 'ACT-040', 'ACT-042', 'PROC-076', 'DUE-001'],
};

export const MOCK_RECOGNITION_FORMS: Record<string, RecognitionFormRead> = { lee };

type JobFields = Pick<
  JobSearchActivity,
  | 'recruitment_contact'
  | 'recruitment_occupation'
  | 'salary_level'
  | 'job_search_method'
  | 'application_method'
  | 'activity_result'
>;

const workJob = (contact: string, occupation: string): JobFields => ({
  recruitment_contact: contact,
  recruitment_occupation: occupation,
  salary_level: null,
  job_search_method: '고용24(워크넷)',
  application_method: '고용24(워크넷)',
  activity_result: '서류전형 심사진행 중',
});

/**
 * 모의 대본이 기록하는 활동(item_id)별 신청서 구직활동 칸. 응모 방식은 2-3.4 매핑을 따릅니다
 * (회사 홈페이지 → 기타). 백엔드는 활동 기록과 신청서 초안을 같은 데이터로 만듭니다.
 */
const JOB_FIELDS: Record<string, JobFields> = {
  a1: workJob('인사팀', '일반 사무'),
  a3: workJob('총무팀', '사무보조'),
  a4: {
    recruitment_contact: '인사팀',
    recruitment_occupation: '기획 사무',
    salary_level: null,
    job_search_method: '취업포탈사이트(민간)',
    application_method: '기타',
    activity_result: '서류전형 심사진행 중',
  },
  a5: {
    recruitment_contact: '총무팀',
    recruitment_occupation: '총무',
    salary_level: null,
    job_search_method: '취업포탈사이트(민간)',
    application_method: '직접방문',
    activity_result: '면접을 본 후 결과를 기다리는 중',
  },
};

/** 구직 외 활동 경로 → 고용24 `과정` 선택지 */
const OTHER_COURSE: Partial<Record<RoundActivity['route'], string>> = {
  step_online: '취업특강(온라인, 오프라인) 수강',
  training: '직업훈련 수강',
};

const EXCLUDED_REASON: Partial<Record<ActivityStatus, ExcludedActivity['reason']>> = {
  same_day: 'same_day',
  out_of_period: 'out_of_period',
  not_allowed: 'not_allowed',
};

/**
 * 패널 B에 기록된 활동으로 신청서 재취업 활동정보를 만듭니다 (시연 검증 1번). 인정된 구직활동은 구직활동내역,
 * 인정된 구직 외 활동은 구직활동 외 활동사항, 계산에서 뺀 활동은 참고로 둡니다. 예정 활동은 넣지 않습니다.
 */
export const buildReemploymentActivity = (
  base: ReemploymentActivity,
  activities: RoundActivity[],
  counted: ReemploymentActivity['counted'],
): ReemploymentActivity => {
  const jobs: JobSearchActivity[] = [];
  const others: OtherActivity[] = [];
  const excluded: ExcludedActivity[] = [];
  for (const activity of activities) {
    const reason = EXCLUDED_REASON[activity.status];
    if (reason) {
      excluded.push({
        item_id: `job_${activity.item_id}`,
        reason,
        activity_date: activity.date,
        company_name: activity.org_name,
      });
    } else if (activity.status !== 'counted') {
      continue;
    } else if (activity.kind === 'job_search') {
      jobs.push({
        item_id: `job_${activity.item_id}`,
        activity_date: activity.date,
        company_name: activity.org_name,
        ...(JOB_FIELDS[activity.item_id] ?? workJob('인사팀', activity.job_title ?? '사무')),
        attachment_ids: activity.evidence.attached,
        source: activity.source === 'work24_import' ? 'work24_import' : 'document',
      });
    } else {
      others.push({
        item_id: `other_${activity.item_id}`,
        course: OTHER_COURSE[activity.route] ?? null,
        details: `${activity.org_name} (${formatShortDate(activity.date)})`,
        attachment_ids: activity.evidence.attached,
        // 온라인 취업특강은 고용24 수강 이력으로 확인돼 증빙이 필요 없습니다 (ACT-043).
        source:
          activity.source === 'work24_import' || activity.route === 'step_online'
            ? 'work24_import'
            : 'conversation',
      });
    }
  }
  return {
    ...base,
    counted,
    has_job_search_activity: jobs.length > 0,
    job_search_activities: jobs,
    excluded,
    has_other_reemployment_activity: others.length > 0,
    other_reemployment_activities: others,
  };
};

/** `GET /forms/recognition` (모의): 기록된 활동이 있으면 그것으로 재취업 활동정보를 바꿔 돌려줍니다. */
export const mockRecognitionForm = (
  personaId: string,
  activityValues: Record<string, unknown>,
): RecognitionFormRead | undefined => {
  const form = MOCK_RECOGNITION_FORMS[personaId];
  const activities = activityValues.activities as RoundActivity[] | undefined;
  if (!form || !activities?.length) return form;
  const base = form.reemployment_activity;
  const counted = {
    activities: Number(activityValues.counted ?? base.counted.activities),
    job_search: Number(activityValues.counted_job_search ?? base.counted.job_search),
  };
  const reemployment = buildReemploymentActivity(base, activities, counted);
  const jobStates = Object.fromEntries(
    reemployment.job_search_activities.map((job) => [
      `reemployment_activity.job_search_activities.${job.item_id}`,
      { status: 'extracted', source: job.source } as const,
    ]),
  );
  const fieldStates = Object.fromEntries(
    Object.entries(form.field_states).filter(
      ([key]) => !key.startsWith('reemployment_activity.job_search_activities.'),
    ),
  );
  return {
    ...form,
    reemployment_activity: reemployment,
    field_states: { ...fieldStates, ...jobStates },
  };
};
