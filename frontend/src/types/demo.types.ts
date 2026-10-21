/**
 * 상세기획 1장(사용자 상태 모델·진입 분기)에 맞춘 임시 타입.
 * 백엔드 API가 올라오면 `pnpm gen:api`로 만든 `api.gen.ts` 타입으로 바꿉니다.
 */

export interface PersonaDisplay {
  name: string;
  age: number;
  job: string;
  quote: string;
  summary: string;
}

/** GET /auth/demo 응답 한 건. 카드 표시용 값만 옵니다. */
export interface PersonaCardRead {
  persona_id: string;
  display: PersonaDisplay;
}

/** POST /auth/demo 요청·응답 */
export interface DemoAuthCreate {
  persona_id: string;
}

export interface DemoAuthRead {
  persona_id: string;
  display: PersonaDisplay;
}

export type Stage =
  | 'job_registration'
  | 'education'
  | 'eligibility_application'
  | 'eligibility_applied'
  | 'recognition';

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
}

export type PanelId = 'A' | 'B' | 'C' | 'E' | 'Q';

export type BranchId =
  'E0' | 'E1' | 'E2' | 'E3' | 'E4a' | 'E4b' | 'E5a' | 'E5b' | 'E6' | 'E7a' | 'E7b';

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
  ui: { big_text: boolean };
  rule_refs: string[];
}

/** POST /sessions 응답 */
export interface SessionRead {
  session_id: string;
  persona_id: string;
  state: UserState;
  derived: DerivedState;
  entry: EntryResult;
}
