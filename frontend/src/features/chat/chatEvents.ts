import { CHAT_ACTIONS } from '@/features/chat/chatActions';
import type { ChatAction } from '@/features/chat/chatReducer';

import { SSE_EVENTS } from '@/lib/sseEvents';
import { type SseMessage, TOOL_STATUS, type ToolCallEvent } from '@/types/chat.types';

/** 말풍선 목록을 바꾸는 이벤트(token·ask_user·done) */
export type BubbleEvent = Extract<
  SseMessage,
  { event: typeof SSE_EVENTS.TOKEN | typeof SSE_EVENTS.ASK_USER | typeof SSE_EVENTS.DONE }
>;

export const isBubbleEvent = (event: SseMessage): event is BubbleEvent =>
  event.event === SSE_EVENTS.TOKEN ||
  event.event === SSE_EVENTS.ASK_USER ||
  event.event === SSE_EVENTS.DONE;

/** SSE 이벤트를 리듀서 액션으로 바꿉니다(순수 함수). */
export const chatActionFor = (event: BubbleEvent): ChatAction => {
  switch (event.event) {
    case SSE_EVENTS.TOKEN:
      return { type: CHAT_ACTIONS.TOKEN, text: event.data.text };
    case SSE_EVENTS.ASK_USER:
      return {
        type: CHAT_ACTIONS.ASK_USER,
        text: event.data.text,
        choices: event.data.choices,
        importKind: event.data.import_kind ?? undefined,
        acceptsFile: event.data.accepts_file,
      };
    case SSE_EVENTS.DONE:
      return { type: CHAT_ACTIONS.DONE, cite: event.data.cite };
  }
};

/** 도구 표시: 시작하면 그 이름, 끝나면 없음. */
export const activeToolAfter = (tool: ToolCallEvent): string | null =>
  tool.status === TOOL_STATUS.STARTED ? tool.name : null;
