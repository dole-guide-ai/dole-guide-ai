/**
 * 대화(SSE) 요청·이벤트 페이로드. 이벤트 이름은 `shared/sse-events.json`, 형태는 상세기획 2-0.7·2-0.10.
 * 백엔드 API가 올라오면 `api.gen.ts` 타입으로 바꿉니다.
 */

export type ChatInputKind = 'text' | 'voice' | 'choice';

/** POST /sessions/{session_id}/chat 본문 */
export interface ChatCreate {
  message: string;
  input_kind: ChatInputKind;
  file_ids?: string[];
}

export interface TokenEvent {
  text: string;
}

export interface ToolCallEvent {
  name: string;
  status: 'started' | 'finished';
}

export interface AskUserEvent {
  question_id: string;
  text: string;
  choices: string[];
}

export type FormKind = 'resume' | 'activities' | 'recognition' | 'procedure';

/** 데이터 설계 필드 확인 상태 6종 (2-0.6) */
export type FieldStatus =
  'missing' | 'extracted' | 'confirmed' | 'conflict' | 'rejected' | 'not_applicable';

export type FieldSource =
  | 'document'
  | 'old_resume'
  | 'conversation'
  | 'self_answer'
  | 'work24_import'
  | 'computed'
  | 'account'
  | 'manual';

export interface FieldEvidence {
  kind: string;
  date?: string;
  quote?: string;
  note?: string;
}

export interface Completeness {
  done: number;
  total: number;
}

export interface FormUpdateEvent {
  form: FormKind;
  path: string;
  op: 'set' | 'append' | 'remove';
  value?: unknown;
  status?: FieldStatus;
  transformed?: boolean;
  source?: FieldSource;
  evidence?: FieldEvidence;
  completeness?: Completeness;
}

/** 말풍선이 끝날 때. 근거 줄(2-0.8)은 여기에 실어 보냅니다. */
export interface DoneEvent {
  cite?: string;
  rule_refs?: string[];
}

export type ChatErrorCode = 'LLM_UNAVAILABLE' | 'RATE_LIMITED' | 'INTERNAL_ERROR';

export interface ErrorEvent {
  code: ChatErrorCode | string;
  message?: string;
}

export type SseMessage =
  | { event: 'token'; data: TokenEvent }
  | { event: 'tool_call'; data: ToolCallEvent }
  | { event: 'ask_user'; data: AskUserEvent }
  | { event: 'form_update'; data: FormUpdateEvent }
  | { event: 'done'; data: DoneEvent }
  | { event: 'error'; data: ErrorEvent };
