import type { FieldEvidence, FieldSource, FieldStatus } from '@/types/chat.types';

/**
 * 실업인정 신청서 초안 (상세기획 2-3.10 · 데이터 설계 `work24_recognition_v1`).
 * 신청인 정보·지급계좌·사업장 연락처는 만들지 않습니다 (2-0.5).
 * 백엔드 API가 올라오면 `api.gen.ts` 타입으로 바꿉니다.
 */

export interface RecognitionInfo {
  recognition_date: string;
  period_start: string;
  period_end: string;
  attendance_round: boolean;
}

/** 실업크레딧 (2-3.2). 수급 개시일 기준 만 60세 이상이면 `is_applicable = false`. */
export interface UnemploymentCredit {
  is_applicable: boolean;
  credit_application_choice: string | null;
  notice_delivery_method: string | null;
  automatic_payment_choice: string | null;
  income_asset_consent: string | null;
  answered_on: string | null;
}

/** 근로 있음 상세 (2-3.3, 고용24 칸): 일한 날·총 근로시간·소득수령(예정)일·소득수령(예정)액 */
export interface WorkDetails {
  work_dates: string | null;
  total_hours: number | null;
  income_date: string | null;
  /** 원 단위 */
  income_amount: number | null;
}

/** 근로 및 취업내역 (2-3.3). 기본값이 없고, 답하기 전에는 null. */
export interface WorkAndEmployment {
  has_work_or_service: boolean | null;
  /** 근로 있음일 때만 */
  work_details?: WorkDetails | null;
  has_employment: boolean | null;
  has_industrial_accident_benefit_right: boolean | null;
  answered_on: string | null;
}

/** 구직활동내역 한 건: 고용24 10칸 + 첨부 (2-3.2 연결 표). 사업장 이메일·전화번호는 두지 않습니다. */
export interface JobSearchActivity {
  item_id: string;
  activity_date: string;
  company_name: string;
  recruitment_contact: string | null;
  recruitment_occupation: string | null;
  salary_level: string | null;
  job_search_method: string | null;
  application_method: string | null;
  activity_result: string | null;
  attachment_ids: string[];
  source: FieldSource;
}

/** 같은 날이라 계산에서 뺀 활동은 신청서에 넣지 않고 참고로만 보여 줍니다. */
export interface ExcludedActivity {
  item_id: string;
  reason: 'same_day' | 'out_of_period' | 'not_allowed';
  activity_date: string;
  company_name: string;
}

export interface OtherActivity {
  item_id: string;
  course: string | null;
  details: string | null;
  attachment_ids: string[];
  source: FieldSource;
}

export interface ReemploymentActivity {
  required: { activities: number; job_search: number };
  counted: { activities: number; job_search: number };
  has_job_search_activity: boolean;
  job_search_activities: JobSearchActivity[];
  excluded: ExcludedActivity[];
  has_other_reemployment_activity: boolean;
  other_reemployment_activities: OtherActivity[];
}

export interface NotificationAndPlan {
  payment_notification_method: string | null;
  desired_reemployment_type: string[];
  next_activity: { value: string | null; memo: string | null; answered_on: string | null };
}

export type ConsentValue = 'agree' | 'disagree' | 'decide_on_work24';

/** 2-3.6 제출 버튼 상태 */
export type SubmitMode = 'attend' | 'preview' | 'send' | 'visit_today' | 'change';

export type ChecklistKey =
  | 'self_answers'
  | 'job_search_fields'
  | 'notification'
  | 'next_activity'
  | 'unemployment_credit'
  | 'requirement_met'
  | 'evidence_ok';

/** 제출 전 확인 한 줄 (2-3.6). `blocking`이면 비었을 때 버튼을 막고, 아니면 경고만. */
export interface ChecklistItem {
  key: ChecklistKey;
  done: boolean;
  blocking: boolean;
}

export type AttendItem = 'id_card' | 'eligibility_card';

export interface FieldMetaRead {
  status: FieldStatus;
  source?: FieldSource;
  transformed?: boolean;
  evidence?: FieldEvidence;
}

/** GET /forms/recognition */
export interface RecognitionFormRead {
  schema_version: 'work24_recognition_v1';
  recognition_round: number;
  status: 'draft' | 'review' | 'finalized';
  recognition_info: RecognitionInfo;
  unemployment_credit: UnemploymentCredit;
  work_and_employment: WorkAndEmployment;
  reemployment_activity: ReemploymentActivity;
  notification_and_plan: NotificationAndPlan;
  personal_information_consent: { value: ConsentValue | null; answered_on: string | null };
  checklist: ChecklistItem[];
  attend_items: AttendItem[];
  submit_mode: SubmitMode;
  can_submit: boolean;
  /** 취업·산재 답으로 작성을 멈췄을 때 (2-3.3 질문 2·3) */
  locked_reason: 'employment' | 'industrial_accident' | null;
  mock_submission: 'sent' | 'attend_ready' | null;
  field_states: Record<string, FieldMetaRead>;
  cite: string;
  rule_refs: string[];
}

/** POST /forms/recognition/confirm 본문 (2-3.10) */
export interface RecognitionConfirmCreate {
  submit_mode: 'send' | 'attend';
}
