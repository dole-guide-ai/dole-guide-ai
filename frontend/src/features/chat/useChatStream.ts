import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import { applyFormUpdateEvent } from '@/features/chat/applyFormUpdateEvent';
import type { ChatAttachment } from '@/features/chat/chat.types';
import { CHAT_ACTIONS } from '@/features/chat/chatActions';
import { describeChatError } from '@/features/chat/chatErrors';
import { chatReducer, initChatState } from '@/features/chat/chatReducer';

import { ApiError } from '@/lib/api';
import { streamChat } from '@/lib/chatStream';
import { ERROR_CODES } from '@/lib/errorCodes';
import { SSE_EVENTS } from '@/lib/sseEvents';
import { type ChatInputKind, INPUT_KIND } from '@/types/chat.types';
import type { SessionRead } from '@/types/demo.types';

export interface SendOptions {
  inputKind?: ChatInputKind;
  /** 올린 파일 ID (2-0.4). 말풍선에는 파일 카드가 붙습니다. */
  fileIds?: string[];
  attachments?: ChatAttachment[];
  /** 고용24 불러오기에서 고른 항목 (2-0.4) */
  importIds?: string[];
}

/**
 * 대화 한 턴: 사용자 말을 보내고 SSE 이벤트를 받아 말풍선·선택지·패널 저장소에 반영합니다 (2-0.3·2-0.7).
 * 입력창 글자도 여기서 들고 있어, 오류가 나면 보낸 글을 그대로 되돌릴 수 있습니다 (2-0.10).
 */
export const useChatStream = (session: SessionRead) => {
  const [state, dispatch] = useReducer(chatReducer, session, initChatState);
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const sessionId = session.session_id;
  const personaId = session.persona_id;

  if (state.sessionId !== sessionId) {
    dispatch({ type: CHAT_ACTIONS.RESET, session });
  }

  useEffect(() => () => abortRef.current?.abort(), [sessionId]);

  /** 업로드 실패처럼 스트림 밖에서 생긴 오류를 말풍선으로 보여 줍니다. */
  const notifySystem = useCallback(
    (text: string) => dispatch({ type: CHAT_ACTIONS.SYSTEM, text }),
    [],
  );

  const send = useCallback(
    async (text: string, options: SendOptions = {}) => {
      const { inputKind = INPUT_KIND.TEXT, fileIds, attachments, importIds } = options;
      const message = text.trim();
      if (!message || abortRef.current) return;

      const controller = new AbortController();
      abortRef.current = controller;
      dispatch({ type: CHAT_ACTIONS.USER_SENT, text: message, inputKind, attachments });
      setInputText('');
      setIsStreaming(true);

      try {
        const stream = await streamChat(
          personaId,
          sessionId,
          { message, input_kind: inputKind, file_ids: fileIds, import_ids: importIds },
          controller.signal,
        );
        for await (const event of stream) {
          if (controller.signal.aborted) break;
          switch (event.event) {
            case SSE_EVENTS.TOKEN:
              dispatch({ type: CHAT_ACTIONS.TOKEN, text: event.data.text });
              break;
            case SSE_EVENTS.TOOL_CALL:
              setActiveTool(event.data.status === 'started' ? event.data.name : null);
              break;
            case SSE_EVENTS.ASK_USER:
              dispatch({
                type: CHAT_ACTIONS.ASK_USER,
                text: event.data.text,
                choices: event.data.choices,
                importKind: event.data.import_kind,
                acceptsFile: event.data.accepts_file,
              });
              break;
            case SSE_EVENTS.FORM_UPDATE:
              applyFormUpdateEvent(event.data);
              break;
            case SSE_EVENTS.DONE:
              dispatch({ type: CHAT_ACTIONS.DONE, cite: event.data.cite });
              break;
            case SSE_EVENTS.ERROR: {
              const described = describeChatError(event.data);
              dispatch({ type: CHAT_ACTIONS.SYSTEM, text: described.text });
              if (described.restoresInput) setInputText(message);
              break;
            }
          }
        }
      } catch (error) {
        if (!controller.signal.aborted) {
          // 턴 시작 전 실패(409 턴 진행 중 등)는 코드별 문구로, 그 밖은 답을 못 만든 것으로 봅니다.
          const notStarted = error instanceof ApiError;
          const described = describeChatError({
            code: notStarted ? error.code : ERROR_CODES.LLM_UNAVAILABLE,
          });
          dispatch({ type: CHAT_ACTIONS.SYSTEM, text: described.text });
          // 턴이 시작되지 않았으면 보낸 글을 항상 되돌려 다시 보낼 수 있게 합니다.
          if (described.restoresInput || notStarted) setInputText(message);
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setActiveTool(null);
        setIsStreaming(false);
      }
    },
    [personaId, sessionId],
  );

  return {
    messages: state.messages,
    choices: state.choices,
    importKind: state.importKind,
    acceptsFile: state.acceptsFile,
    isStreaming,
    activeTool,
    inputText,
    setInputText,
    send,
    notifySystem,
  };
};
