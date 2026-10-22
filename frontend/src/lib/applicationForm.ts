/**
 * 백엔드 회차 신청서(`ApplicationRead`, F-23)를 패널 C가 쓰는 신청서 모양(`RecognitionFormRead`)으로 바꾸는
 * 임시 어댑터입니다. 패널 C가 아직 예전 신청서 구조를 쓰고 있어서 둔 것이며, 화면을 새 API 타입으로 옮기면 지웁니다.
 * 백엔드는 선택지를 코드(wish·sms 등)로 저장하고, 화면은 고용24 화면 글자(희망함·휴대전화 문자메시지)로 보여 줍니다.
 */

import { citeOf } from '@/lib/sources';
import type { components } from '@/types/api.gen';
import type { FieldSource } from '@/types/chat.types';
import type {
  ChecklistItem,
  ChecklistKey,
  ConsentValue,
  FieldMetaRead,
  RecognitionFormRead,
} from '@/types/recognition.types';

type ApplicationRead = components['schemas']['ApplicationRead'];
type FormField = components['schemas']['FormField'];

const CREDIT_CHOICE: Record<string, string> = { wish: '희망함', not_wish: '희망하지 않음' };
const NOTICE_METHOD: Record<string, string> = { electronic: '전자고지', mail: '우편' };
const CONSENT: Record<string, string> = { agree: '동의함', disagree: '동의하지 않음' };
const NOTIFICATION: Record<string, string> = {
  sms: '휴대전화 문자메시지',
  email: '전자우편',
  mail: '우편',
};
const PRIVACY: Record<string, ConsentValue> = { agree_all: 'agree', disagree: 'disagree' };
const OTHER_COURSE: Record<string, string> = {
  lecture: '취업특강(온라인, 오프라인) 수강',
  training: '직업훈련 수강',
  counseling: '집단상담 프로그램 참여',
  aptitude_test: '직업심리검사',
  volunteer: '고용센터 담당자가 지시한 사회봉사활동',
};
const WORK24_METHOD = '고용24(워크넷)';

const value = (field: FormField | undefined): unknown => field?.value ?? null;
const text = (field: FormField | undefined, labels: Record<string, string>): string | null => {
  const raw = value(field);
  return typeof raw === 'string' ? (labels[raw] ?? raw) : null;
};
const yesNo = (field: FormField | undefined): boolean | null => {
  const raw = value(field);
  return raw === 'yes' ? true : raw === 'no' ? false : null;
};

/** 지난 회차에서 불러온 본인 답변이면 `지난 답 · 날짜` 칩이 붙도록 칸 상태를 만듭니다. */
const previousAnswer = (field: FormField | undefined): FieldMetaRead | undefined =>
  field?.answered_on && field.value != null
    ? {
        status: 'confirmed',
        source: 'self_answer',
        evidence: { kind: 'previous_round', date: field.answered_on, note: '지난 회차에 답한 값' },
      }
    : undefined;

/** 제출 전 확인 7줄 (2-3.6). 앞 4줄은 비면 제출을 막고, 뒤 3줄은 경고만 합니다. */
const CHECKLIST_KEYS: { key: ChecklistKey; blocking: boolean }[] = [
  { key: 'self_answers', blocking: true },
  { key: 'job_search_fields', blocking: true },
  { key: 'notification', blocking: true },
  { key: 'next_activity', blocking: true },
  { key: 'unemployment_credit', blocking: false },
  { key: 'requirement_met', blocking: false },
  { key: 'evidence_ok', blocking: false },
];

/** 서버는 남은 항목(막는 항목·경고)만 주므로, 목록에 없는 줄은 마친 것으로 봅니다 (F-26). */
const checklistItems = (app: ApplicationRead): ChecklistItem[] => {
  const remaining = new Set(
    [...app.checklist.blocking, ...app.checklist.warnings].map((item) => item.key),
  );
  return CHECKLIST_KEYS.map(({ key, blocking }) => ({ key, blocking, done: !remaining.has(key) }));
};

export const recognitionFromApplication = (app: ApplicationRead): RecognitionFormRead => {
  const { data } = app;
  const credit = data.credit;
  const entries = value(data.work.entries);
  const firstWork = Array.isArray(entries)
    ? (entries[0] as Record<string, unknown> | undefined)
    : undefined;
  const employment = value(data.employment.status);
  const jobSearch = app.job_search_rows.map((row) => ({
    item_id: row.activity_id,
    activity_date: row.activity_date,
    company_name: row.company_name ?? '',
    recruitment_contact: row.recruitment_contact ?? null,
    recruitment_occupation: row.recruitment_occupation ?? null,
    salary_level: row.salary_level ?? null,
    job_search_method: row.job_search_method ?? null,
    application_method: row.application_method ?? null,
    activity_result: row.activity_result ?? null,
    attachment_ids: row.file_ids ?? [],
    source: (row.application_method === WORK24_METHOD
      ? 'work24_import'
      : 'document') as FieldSource,
  }));

  const fieldStates: Record<string, FieldMetaRead> = {};
  const creditState = previousAnswer(credit.application);
  if (creditState) fieldStates.unemployment_credit = creditState;
  const notificationState = previousAnswer(data.notification_method);
  if (notificationState) {
    fieldStates['notification_and_plan.payment_notification_method'] = notificationState;
  }
  for (const row of jobSearch) {
    fieldStates[`reemployment_activity.job_search_activities.${row.item_id}`] = {
      status: 'extracted',
      source: row.source,
    };
  }

  return {
    schema_version: 'work24_recognition_v1',
    recognition_round: app.round,
    status: app.status === 'submitted' ? 'finalized' : 'review',
    recognition_info: {
      recognition_date: app.recognition_date,
      period_start: app.period_start,
      period_end: app.period_end,
      attendance_round: app.attendance_required,
    },
    unemployment_credit: {
      is_applicable: value(credit.application) !== 'not_applicable',
      credit_application_choice: text(credit.application, CREDIT_CHOICE),
      notice_delivery_method: text(credit.notice_method, NOTICE_METHOD),
      automatic_payment_choice: text(credit.auto_payment, CREDIT_CHOICE),
      income_asset_consent: text(credit.income_asset_consent, CONSENT),
      answered_on: credit.application?.answered_on ?? null,
    },
    work_and_employment: {
      has_work_or_service: yesNo(data.work.has_work),
      work_details: firstWork
        ? {
            work_dates: (firstWork.worked_on as string | undefined) ?? null,
            total_hours: (firstWork.hours as number | undefined) ?? null,
            income_date: (firstWork.income_received_on as string | undefined) ?? null,
            income_amount: (firstWork.amount as number | undefined) ?? null,
          }
        : null,
      has_employment: employment == null ? null : employment !== 'none',
      has_industrial_accident_benefit_right: yesNo(data.industrial_accident.receiving),
      answered_on: data.work.has_work?.answered_on ?? null,
    },
    reemployment_activity: {
      required: { activities: app.required_activities, job_search: app.required_job_search },
      counted: {
        activities: jobSearch.length + app.other_rows.length,
        job_search: jobSearch.length,
      },
      has_job_search_activity: jobSearch.length > 0,
      job_search_activities: jobSearch,
      excluded: app.excluded_rows.map((row) => ({
        item_id: row.activity_id,
        reason: row.reason as 'same_day' | 'out_of_period' | 'not_allowed',
        activity_date: row.activity_date,
        company_name: row.company_name ?? '',
      })),
      has_other_reemployment_activity: app.other_rows.length > 0,
      other_reemployment_activities: app.other_rows.map((row) => ({
        item_id: row.activity_id,
        course: OTHER_COURSE[row.kind] ?? null,
        details: row.details ?? null,
        attachment_ids: [],
        source: 'conversation' as FieldSource,
      })),
    },
    notification_and_plan: {
      payment_notification_method: text(data.notification_method, NOTIFICATION),
      desired_reemployment_type: [],
      next_activity: { value: null, memo: null, answered_on: null },
    },
    personal_information_consent: {
      value: PRIVACY[String(value(data.privacy_consent))] ?? null,
      answered_on: data.privacy_consent?.answered_on ?? null,
    },
    checklist: checklistItems(app),
    attend_items: app.attendance_required ? ['id_card', 'eligibility_card'] : [],
    submit_mode: app.submit_mode,
    can_submit: app.can_submit,
    locked_reason: app.locked_reason === 'employed' ? 'employment' : (app.locked_reason ?? null),
    mock_submission:
      app.status === 'submitted' ? (app.attendance_required ? 'attend_ready' : 'sent') : null,
    field_states: fieldStates,
    cite: citeOf('SRC-001', 'SRC-016'),
    rule_refs: [],
  };
};
