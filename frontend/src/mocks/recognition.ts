import type { RecognitionFormRead } from '@/types/recognition.types';

/**
 * 실업인정 신청서 모의 스냅샷 (상세기획 2-3.10, 시안 2-3-1 시점). 이정호 4차, 출석 회차, 기준일 12.16 10:00.
 * 본인 답변(근로·취업·산재)과 다음 출석일까지 활동은 비어 있고, 실업크레딧·통지방법은 3차(11.24) 답이 남아 있습니다.
 * 제출 버튼 상태·제출 가능 여부는 백엔드 `submit_mode`·`can_submit` 결과를 흉내 낸 값입니다.
 */
const SOURCE_FORM = '고용24 실업급여(상용직) · 취업드림수첩 2025';

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
