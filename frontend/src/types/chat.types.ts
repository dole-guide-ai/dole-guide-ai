/**
 * 대화(SSE) 요청·이벤트 페이로드. 이벤트 이름은 `shared/sse-events.json`, 형태는 상세기획 2-0.7·2-0.10.
 * 백엔드 API가 올라오면 `api.gen.ts` 타입으로 바꿉니다.
 */

import type { ERROR_CODES } from '@/lib/errorCodes';
import type { SSE_EVENTS } from '@/lib/sseEvents';
import type { components } from '@/types/api.gen';
import type { ImportKind } from '@/types/imports.types';

export const INPUT_KIND = { TEXT: 'text', VOICE: 'voice', CHOICE: 'choice' } as const;

export type ChatInputKind = (typeof INPUT_KIND)[keyof typeof INPUT_KIND];

/** `POST /accounts/{persona_id}/messages` 본문. 백엔드 스키마(api.gen)를 그대로 씁니다. */
export type MessageCreate = components['schemas']['MessageCreate'];

export const TOOL_STATUS = { STARTED: 'started', FINISHED: 'finished' } as const;

export interface TokenEvent {
  text: string;
}

export interface ToolCallEvent {
  name: string;
  status: (typeof TOOL_STATUS)[keyof typeof TOOL_STATUS];
}

/**
 * 질문 이벤트이자 새로고침 뒤 멈춘 질문(`AccountRead.pending_ask`). 백엔드 스키마를 그대로 쓰고,
 * 불러오기 종류만 화면이 아는 값으로 좁힙니다.
 * - `import_kind`: 고용24 불러오기 목록을 열 때 (2-0.4)
 * - `accepts_file`: 서류·사진을 요청할 때만 true. 이때만 `파일 올리기`를 켭니다 (2-0.4)
 */
export type AskUserEvent = Omit<
  components['schemas']['AskUserEvent'],
  'import_kind' | 'accepts_file'
> & {
  import_kind?: ImportKind | null;
  accepts_file?: boolean;
};

export type FormKind = 'resume' | 'activities' | 'recognition' | 'procedure';

/** 데이터 설계 필드 확인 상태 6종 (2-0.6) */
export type FieldStatus =
  'missing' | 'extracted' | 'confirmed' | 'conflict' | 'rejected' | 'not_applicable';

/** 칸 값의 출처. 백엔드 `FieldSource`와 같은 이름입니다 (API·ERD 설계). */
export type FieldSource = components['schemas']['FieldSource'];

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

/** 백엔드(JSON Patch: add·replace·remove)와 예전 화면 연산(set·append)을 함께 받습니다. */
export type FormUpdateOp = components['schemas']['FormUpdate']['op'] | 'set' | 'append';

export interface FormUpdateEvent {
  form: FormKind;
  path: string;
  op: FormUpdateOp;
  value?: unknown;
  status?: FieldStatus;
  transformed?: boolean;
  source?: FieldSource;
  evidence?: FieldEvidence;
  completeness?: Completeness;
}

/** 말풍선이 끝날 때. 근거 줄(2-0.8)은 여기에 실어 보냅니다. */
/** 근거 줄에서 열어 볼 원문 (RAG 검색 자료) */
export interface CiteLink {
  title: string;
  url?: string | null;
  updated_on?: string | null;
}

export interface DoneEvent {
  cite?: string;
  rule_refs?: string[];
  cite_links?: CiteLink[];
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

export type ChatErrorCode =
  | typeof ERROR_CODES.LLM_UNAVAILABLE
  | typeof ERROR_CODES.RATE_LIMITED
  | typeof ERROR_CODES.TIMEOUT
  | typeof ERROR_CODES.INTERNAL_ERROR;

export interface ErrorEvent {
  code: ChatErrorCode | string;
  message?: string;
}

export type SseMessage =
  | { event: typeof SSE_EVENTS.TOKEN; data: TokenEvent }
  | { event: typeof SSE_EVENTS.TOOL_CALL; data: ToolCallEvent }
  | { event: typeof SSE_EVENTS.ASK_USER; data: AskUserEvent }
  | { event: typeof SSE_EVENTS.FORM_UPDATE; data: FormUpdateEvent }
  | { event: typeof SSE_EVENTS.DONE; data: DoneEvent }
  | { event: typeof SSE_EVENTS.ERROR; data: ErrorEvent };
