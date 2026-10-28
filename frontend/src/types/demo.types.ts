import type { components } from '@/types/api.gen';
import type { AskUserEvent } from '@/types/chat.types';

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

/** 1.2 상태 값 (서버 `ProcedureRead`·`RoundSummary` 그대로) */
export interface UserState {
  stage: Stage;
  education_done: boolean;
  eligibility_applied_date: string | null;
  next_recognition_date: string | null;
}

export interface DatePeriod {
  start: string;
  end: string;
}

/** 1.2 파생값. 판정은 모두 서버가 하고 여기서는 계산하지 않습니다(`lib/accountSession.ts`). */
export interface DerivedState {
  current_round: number | null;
  /** 인정일까지 남은 날(서버 `deadline.d_day`) */
  d_day: number | null;
  /** 인정일 당일 18시가 지나 변경 신청만 남음(서버 `deadline.overdue`) */
  is_overdue: boolean;
  period: DatePeriod | null;
  is_attendance_round: boolean;
  /** 인터넷 사전제출 대상(이직일 만 65세 미만, PROC-048 · 서버 `procedure.online_presubmit`) */
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
  /** 누르면 파일 선택창을 여는 보기 (질문의 `file_choice`와 같음) */
  file_choice?: string | null;
  /**
   * 새로고침 전 답을 기다리던 질문 (F-03, `AccountRead.pending_ask`). 있으면 그 선택지·불러오기 종류를 다시 띄우고,
   * 없으면 저장된 대화를 되살릴 때 진입 선택지를 지웁니다.
   */
  pending_ask?: Pick<
    AskUserEvent,
    'choices' | 'import_kind' | 'accepts_file' | 'file_choice'
  > | null;
  ui: { big_text: boolean };
  rule_refs: string[];
}

/** 대시보드 알림(서버 `AccountRead.notices`). 무엇을 알릴지·문구·근거는 서버가 정합니다. */
export type Notice = components['schemas']['Notice'];

/** 화면이 쓰는 세션. `AccountRead`에서 만듭니다(`lib/accountSession.ts`). */
export interface SessionRead {
  session_id: string;
  persona_id: string;
  state: UserState;
  derived: DerivedState;
  notices: Notice[];
  entry: EntryResult;
}
