import type { ImportKind } from '@/types/imports.types';

/**
 * 상세기획 1장(사용자 상태 모델·진입 분기)에 맞춘 임시 타입.
 * 백엔드 API가 올라오면 `pnpm gen:api`로 만든 `api.gen.ts` 타입으로 바꿉니다.
 */

export type Stage =
  | 'job_registration'
  | 'education'
  | 'eligibility_application'
  | 'eligibility_applied'
  | 'recognition'
  | 'ended';

export type ResumeStatus = 'none' | 'outdated' | 'draft' | 'ready';

export type RecipientType = 'general' | 'repeat';

/** 1.2 상태 값 */
export interface UserState {
  separation_date: string;
  age_at_separation: number;
  has_disability: boolean;
  recipient_type: RecipientType;
  employment_type: 'regular';
  stage: Stage;
  resume_status: ResumeStatus;
  education_done: boolean;
  eligibility_applied_date: string | null;
  completed_rounds: number;
  last_recognition_date: string | null;
  next_recognition_date: string | null;
  demo_today: string;
  demo_time: string;
}

export type RuleGroup = 'general' | 'age_60_64' | 'age65_or_disabled';

export interface DatePeriod {
  start: string;
  end: string;
}

/** 1.2 파생값 */
export interface DerivedState {
  rule_group: RuleGroup;
  rule_set: string | null;
  current_round: number | null;
  d_day: number | null;
  period: DatePeriod | null;
  is_attendance_round: boolean;
  required: number | null;
  required_job_search: number | null;
  can_presubmit_online: boolean;
  /** 수급 종료 예정일(급여 소진일·수급기간 끝 중 이른 날), 남은 회차(이번 포함), 마지막 회차 (F-33) */
  expected_end_date?: string | null;
  remaining_rounds?: number | null;
  last_round?: number | null;
  end_reason?: 'exhausted' | 'period_expired' | 'employed' | null;
}

export type PanelId = 'A' | 'B' | 'C' | 'E' | 'Q';

export type BranchId =
  'E0' | 'E1' | 'E2' | 'E3' | 'E4a' | 'E4b' | 'E5a' | 'E5b' | 'E6' | 'E7a' | 'E7b' | 'E7c' | 'END';

export type ProgressStep = 1 | 2 | 3 | 4;

export interface EntryMessage {
  template_id: string;
  text: string;
  cite?: string;
}

/** 1.11 진입 결과 */
export interface EntryResult {
  branch_id: BranchId;
  panel: PanelId | null;
  progress: { current: ProgressStep; done: ProgressStep[] };
  title: string;
  next_step_text: string;
  messages: EntryMessage[];
  choices: string[];
  /** 첫 안내가 서류·사진을 요청하면 true (2-0.4 `accepts_file`과 같은 뜻) */
  accepts_file?: boolean;
  /**
   * 새로고침 전 답을 기다리던 질문 (F-03, `AccountRead.pending_ask`). 있으면 그 선택지·불러오기 종류를 다시 띄우고,
   * 없으면 저장된 대화를 되살릴 때 진입 선택지를 지웁니다.
   */
  pending_ask?: { choices: string[]; import_kind: ImportKind | null } | null;
  ui: { big_text: boolean };
  rule_refs: string[];
}

/** 화면이 쓰는 세션. `AccountRead`에서 만듭니다(`lib/accountSession.ts`). */
export interface SessionRead {
  session_id: string;
  persona_id: string;
  state: UserState;
  derived: DerivedState;
  entry: EntryResult;
}
