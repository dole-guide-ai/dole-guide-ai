import type { ChatAttachment, ChatMessage } from '@/features/chat/chat.types';
import { CHAT_ROLE } from '@/features/chat/chat.types';
import { CHAT_ACTIONS } from '@/features/chat/chatActions';

import type { ChatInputKind } from '@/types/chat.types';
import type { EntryResult, SessionRead } from '@/types/demo.types';
import type { ImportKind } from '@/types/imports.types';

/**
 * 말풍선 목록·선택지·스트리밍 중인 말풍선을 다루는 순수 리듀서.
 * `token`은 스트리밍 중인 말풍선에 이어 붙이고, `ask_user`는 질문 말풍선과 선택지를 만들고,
 * `done`은 말풍선을 닫으며 근거 줄을 답니다 (2-0.7).
 */
export interface ChatState {
  sessionId: string;
  messages: ChatMessage[];
  choices: string[];
  /** 마지막 질문이 고용24 불러오기 목록을 열었으면 그 종류 (2-0.4) */
  importKind: ImportKind | null;
  /** 마지막 질문이 서류·사진을 요청했는지 (2-0.4 `accepts_file`). 이때만 파일 올리기를 켭니다. */
  acceptsFile: boolean;
  streamingId: string | null;
  nextId: number;
}

export type ChatAction =
  | { type: typeof CHAT_ACTIONS.RESET; session: SessionRead }
  /**
   * 새로고침 뒤 서버에 저장된 대화로 말풍선을 되살립니다 (F-03).
   * 선택지·불러오기 종류는 멈춘 질문(`pending_ask`)의 것만 남기고, 답을 마친 대화면 비웁니다.
   */
  | {
      type: typeof CHAT_ACTIONS.RESTORE;
      messages: ChatMessage[];
      pendingAsk: EntryResult['pending_ask'];
    }
  | {
      type: typeof CHAT_ACTIONS.USER_SENT;
      text: string;
      inputKind: ChatInputKind;
      attachments?: ChatAttachment[];
    }
  | { type: typeof CHAT_ACTIONS.TOKEN; text: string }
  | {
      type: typeof CHAT_ACTIONS.USER_SENT;
      text: string;
      inputKind: ChatInputKind;
      attachments?: ChatAttachment[];
    }
  | { type: typeof CHAT_ACTIONS.TOKEN; text: string }
  | {
      type: typeof CHAT_ACTIONS.ASK_USER;
      text: string;
      choices: string[];
      importKind?: ImportKind;
      acceptsFile?: boolean;
    }
  | { type: typeof CHAT_ACTIONS.DONE; cite?: string }
  | { type: typeof CHAT_ACTIONS.SYSTEM; text: string };

export const initChatState = (session: SessionRead): ChatState => ({
  sessionId: session.session_id,
  messages: session.entry.messages.map((message, index) => ({
    id: `entry-${index}`,
    role: CHAT_ROLE.ASSISTANT,
    text: message.text,
    cite: message.cite,
  })),
  choices: session.entry.choices,
  importKind: session.entry.pending_ask?.import_kind ?? null,
  acceptsFile: session.entry.pending_ask?.accepts_file ?? session.entry.accepts_file ?? false,
  streamingId: null,
  nextId: 1,
});

/** 스트리밍 중이던 말풍선을 닫습니다. 글자가 없으면 지웁니다. */
const closeStreaming = (state: ChatState): ChatState => {
  if (!state.streamingId) return state;
  const messages = state.messages.filter(
    (message) => message.id !== state.streamingId || message.text.length > 0,
  );
  return { ...state, messages, streamingId: null };
};

const push = (state: ChatState, message: Omit<ChatMessage, 'id'>): ChatState => ({
  ...state,
  messages: [...state.messages, { ...message, id: `m-${state.nextId}` }],
  nextId: state.nextId + 1,
});

export const chatReducer = (state: ChatState, action: ChatAction): ChatState => {
  switch (action.type) {
    case CHAT_ACTIONS.RESET:
      return initChatState(action.session);

    case CHAT_ACTIONS.RESTORE:
      // 이미 이번 화면에서 대화를 이어 갔으면 덮어쓰지 않습니다.
      if (state.messages.some((message) => message.role === CHAT_ROLE.USER) || state.streamingId) {
        return state;
      }
      return {
        ...state,
        messages: action.messages,
        choices: action.pendingAsk?.choices ?? [],
        importKind: action.pendingAsk?.import_kind ?? null,
        acceptsFile: action.pendingAsk?.accepts_file ?? false,
      };

    case CHAT_ACTIONS.USER_SENT:
      return {
        ...push(closeStreaming(state), {
          role: CHAT_ROLE.USER,
          text: action.text,
          inputKind: action.inputKind,
          attachments: action.attachments,
        }),
        choices: [],
        importKind: null,
        acceptsFile: false,
      };

    case CHAT_ACTIONS.TOKEN: {
      if (state.streamingId) {
        return {
          ...state,
          messages: state.messages.map((message) =>
            message.id === state.streamingId
              ? { ...message, text: message.text + action.text }
              : message,
          ),
        };
      }
      const started = push(state, { role: CHAT_ROLE.ASSISTANT, text: action.text });
      return { ...started, streamingId: `m-${state.nextId}` };
    }

    case CHAT_ACTIONS.ASK_USER:
      return {
        ...push(closeStreaming(state), { role: CHAT_ROLE.ASSISTANT, text: action.text }),
        choices: action.choices,
        importKind: action.importKind ?? null,
        acceptsFile: action.acceptsFile ?? false,
      };

    case CHAT_ACTIONS.DONE: {
      const targetId =
        state.streamingId ??
        [...state.messages].reverse().find((m) => m.role === CHAT_ROLE.ASSISTANT)?.id;
      const withCite = action.cite
        ? {
            ...state,
            messages: state.messages.map((message) =>
              message.id === targetId ? { ...message, cite: action.cite } : message,
            ),
          }
        : state;
      return closeStreaming(withCite);
    }

    case CHAT_ACTIONS.SYSTEM:
      return push(closeStreaming(state), { role: CHAT_ROLE.SYSTEM, text: action.text });
  }
};
