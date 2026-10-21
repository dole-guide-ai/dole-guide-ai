import type { ChatAttachment, ChatMessage } from '@/features/chat/chat.types';

import type { ChatInputKind } from '@/types/chat.types';
import type { SessionRead } from '@/types/demo.types';
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
  | { type: 'reset'; session: SessionRead }
  | { type: 'user_sent'; text: string; inputKind: ChatInputKind; attachments?: ChatAttachment[] }
  | { type: 'token'; text: string }
  | {
      type: 'ask_user';
      text: string;
      choices: string[];
      importKind?: ImportKind;
      acceptsFile?: boolean;
    }
  | { type: 'done'; cite?: string }
  | { type: 'system'; text: string };

export const initChatState = (session: SessionRead): ChatState => ({
  sessionId: session.session_id,
  messages: session.entry.messages.map((message, index) => ({
    id: `entry-${index}`,
    role: 'assistant',
    text: message.text,
    cite: message.cite,
  })),
  choices: session.entry.choices,
  importKind: null,
  acceptsFile: session.entry.accepts_file ?? false,
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
    case 'reset':
      return initChatState(action.session);

    case 'user_sent':
      return {
        ...push(closeStreaming(state), {
          role: 'user',
          text: action.text,
          inputKind: action.inputKind,
          attachments: action.attachments,
        }),
        choices: [],
        importKind: null,
        acceptsFile: false,
      };

    case 'token': {
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
      const started = push(state, { role: 'assistant', text: action.text });
      return { ...started, streamingId: `m-${state.nextId}` };
    }

    case 'ask_user':
      return {
        ...push(closeStreaming(state), { role: 'assistant', text: action.text }),
        choices: action.choices,
        importKind: action.importKind ?? null,
        acceptsFile: action.acceptsFile ?? false,
      };

    case 'done': {
      const targetId =
        state.streamingId ?? [...state.messages].reverse().find((m) => m.role === 'assistant')?.id;
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

    case 'system':
      return push(closeStreaming(state), { role: 'system', text: action.text });
  }
};
