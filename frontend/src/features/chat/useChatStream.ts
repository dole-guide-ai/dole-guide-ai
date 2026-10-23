import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import { applyFormUpdateEvent } from '@/features/chat/applyFormUpdateEvent';
import type { ChatAttachment } from '@/features/chat/chat.types';
import { CHAT_ACTIONS } from '@/features/chat/chatActions';
import { describeChatError } from '@/features/chat/chatErrors';
import { activeToolAfter, chatActionFor, isBubbleEvent } from '@/features/chat/chatEvents';
import { chatReducer, initChatState } from '@/features/chat/chatReducer';
import { useChatHistory } from '@/features/chat/useChatHistory';

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

  // F-03: 새로고침 뒤에는 서버에 저장된 대화로 말풍선을 되살립니다. 저장된 대화가 없으면 진입 안내를 둡니다.
  const history = useChatHistory(session);
  const pendingAsk = session.entry.pending_ask;
  useEffect(() => {
    if (history.data?.length)
      dispatch({ type: CHAT_ACTIONS.RESTORE, messages: history.data, pendingAsk });
  }, [history.data, pendingAsk]);
  // 이전 대화를 못 받으면 대화가 없던 것처럼 보이지 않게 서버 문구를 말풍선으로 알립니다.
  useEffect(() => {
    if (!history.error) return;
    dispatch({
      type: CHAT_ACTIONS.SYSTEM,
      text:
        history.error instanceof ApiError
          ? history.error.message
          : '이전 대화를 불러오지 못했어요. 새로고침해 주세요.',
    });
  }, [history.error]);

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

      /** 오류 문구를 말풍선으로 보이고, 필요하면 보낸 글을 입력창에 되돌립니다. */
      const showError = (code: string, restore = false) => {
        const described = describeChatError({ code });
        dispatch({ type: CHAT_ACTIONS.SYSTEM, text: described.text });
        if (described.restoresInput || restore) setInputText(message);
      };

      try {
        const stream = await streamChat(
          personaId,
          {
            text: message,
            input_kind: inputKind,
            file_ids: fileIds ?? [],
            import_ids: importIds ?? [],
          },
          controller.signal,
        );
        for await (const event of stream) {
          if (controller.signal.aborted) break;
          if (isBubbleEvent(event)) dispatch(chatActionFor(event));
          else if (event.event === SSE_EVENTS.TOOL_CALL) setActiveTool(activeToolAfter(event.data));
          else if (event.event === SSE_EVENTS.FORM_UPDATE) applyFormUpdateEvent(event.data);
          else if (event.event === SSE_EVENTS.ERROR) showError(event.data.code);
        }
      } catch (error) {
        // 턴 시작 전 실패(409 턴 진행 중 등)는 코드별 문구로 알리고 보낸 글을 되돌립니다.
        // 그 밖(연결 끊김 등)은 답을 못 만든 것으로 봅니다.
        if (!controller.signal.aborted) {
          if (error instanceof ApiError) showError(error.code, true);
          else showError(ERROR_CODES.LLM_UNAVAILABLE);
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setActiveTool(null);
        setIsStreaming(false);
      }
    },
    [personaId],
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
