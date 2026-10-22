/**
 * 대화(SSE) 요청·이벤트 페이로드. 이벤트 이름은 `shared/sse-events.json`, 형태는 상세기획 2-0.7·2-0.10.
 * 백엔드 API가 올라오면 `api.gen.ts` 타입으로 바꿉니다.
 */

import type { ImportKind } from '@/types/imports.types';

export type ChatInputKind = 'text' | 'voice' | 'choice';

/** POST /sessions/{session_id}/chat 본문 */
export interface ChatCreate {
  message: string;
  input_kind: ChatInputKind;
  file_ids?: string[];
  /** 고용24 불러오기 목록에서 고른 항목 (2-0.4). 고른 것만 보냅니다. */
  import_ids?: string[];
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
  /** 고용24 불러오기 목록을 열 때 (2-0.4). 대화창 안에서 고르게 합니다. */
  import_kind?: ImportKind;
  /** 이 질문이 서류·사진을 요청할 때만 true (2-0.4). 프론트는 이때만 `파일 올리기`를 켭니다. */
  accepts_file?: boolean;
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

/** POST /files 응답 (2-0.11). 판독 진행은 백엔드가 대화 응답의 `tool_call`(parse_file)로 알립니다. */
export interface FileUploadRead {
  file_id: string;
  job_id: string;
}

/** PATCH /forms/{kind} 본문 (2-0.6 패널에서 직접 고치기) */
export interface FormPatchCreate {
  path: string;
  op: 'set' | 'remove';
  value?: unknown;
}

/** PATCH /forms/{kind} 응답: 적용할 `form_update`들 (값 정리 결과·완성도 포함) */
export interface FormPatchRead {
  updates: FormUpdateEvent[];
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
