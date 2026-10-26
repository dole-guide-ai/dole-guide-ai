import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import { useQueryClient } from '@tanstack/react-query';

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
import { queryKeys } from '@/lib/queryKeys';
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
  const queryClient = useQueryClient();
  const sessionId = session.session_id;
  const personaId = session.persona_id;

  if (state.sessionId !== sessionId) {
    dispatch({ type: CHAT_ACTIONS.RESET, session });
  }

  // 실제 서버 세션: 이력서 저장처럼 같은 대화 안에서 첫 안내가 새로 오면 말풍선으로 이어 붙입니다.
  // 세션이 바뀐 경우는 위의 reset이 첫 안내를 새로 깔므로 붙이지 않습니다.
  const entryRef = useRef({ sessionId, messages: session.entry.messages });
  useEffect(() => {
    const prev = entryRef.current;
    entryRef.current = { sessionId, messages: session.entry.messages };
    if (prev.sessionId !== sessionId || prev.messages === session.entry.messages) return;
    dispatch({ type: CHAT_ACTIONS.ENTRY, entry: session.entry });
  }, [session.entry, sessionId]);

  // F-03: 새로고침 뒤에는 서버에 저장된 대화로 말풍선을 되살립니다. 저장된 대화가 없으면 진입 안내를 둡니다.
  const history = useChatHistory(session);
  useEffect(() => {
    // 답을 기다리던 질문은 기록의 마지막 말풍선으로 정합니다(로그인 때 세션 값은 그 뒤 대화를 모름).
    if (history.data?.messages.length)
      dispatch({
        type: CHAT_ACTIONS.RESTORE,
        messages: history.data.messages,
        pendingAsk: history.data.pendingAsk,
      });
  }, [history.data]);
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
      // 대화가 이력서를 고치면 서버 버전(lock_version)이 오릅니다. 턴이 끝나면 이력서를 다시 받아
      // 패널 직접 고치기의 If-Match가 옛 버전으로 409를 받지 않게 합니다.
      let resumeChanged = false;
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
          else if (event.event === SSE_EVENTS.FORM_UPDATE) {
            applyFormUpdateEvent(event.data);
            resumeChanged ||= event.data.form === 'resume';
          } else if (event.event === SSE_EVENTS.ERROR) showError(event.data.code);
        }
      } catch (error) {
        // 턴 시작 전 실패(409 턴 진행 중 등)는 보낸 말풍선을 지우고 글을 입력창에 되돌립니다.
        // 그 밖(연결 끊김 등)은 답을 못 만든 것으로 봅니다.
        if (!controller.signal.aborted) {
          if (error instanceof ApiError) {
            dispatch({ type: CHAT_ACTIONS.SEND_REJECTED });
            showError(error.code, true);
          } else showError(ERROR_CODES.LLM_UNAVAILABLE);
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        if (resumeChanged) {
          void queryClient.invalidateQueries({ queryKey: queryKeys.resumeForm(sessionId) });
        }
        setActiveTool(null);
        setIsStreaming(false);
      }
    },
    [personaId, queryClient, sessionId],
  );

  return {
    messages: state.messages,
    choices: state.choices,
    question: state.question,
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
