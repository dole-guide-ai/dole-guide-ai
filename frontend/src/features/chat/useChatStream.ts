import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import { applyFormUpdateEvent } from '@/features/chat/applyFormUpdateEvent';
import type { ChatAttachment } from '@/features/chat/chat.types';
import { describeChatError } from '@/features/chat/chatErrors';
import { chatReducer, initChatState } from '@/features/chat/chatReducer';
import { useChatHistory } from '@/features/chat/useChatHistory';

import { isServerSession } from '@/lib/accountSession';
import { ApiError } from '@/lib/api';
import { streamChat } from '@/lib/chatStream';
import type { ChatInputKind } from '@/types/chat.types';
import type { SessionRead } from '@/types/demo.types';
import { loadMockChat, saveMockChat } from '@/mocks/mockPersistence';

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
  // 모의 화면은 서버가 없어 탭에 둔 대화로 새로고침 전 화면을 되살립니다 (F-03).
  const [state, dispatch] = useReducer(chatReducer, session, (initial) =>
    isServerSession(initial.session_id)
      ? initChatState(initial)
      : (loadMockChat(initial.session_id) ?? initChatState(initial)),
  );
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [inputText, setInputText] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const sessionId = session.session_id;

  if (state.sessionId !== sessionId) {
    dispatch({ type: 'reset', session });
  }

  // F-03: 새로고침 뒤에는 서버에 저장된 대화로 말풍선을 되살립니다. 저장된 대화가 없으면 진입 안내를 둡니다.
  // 모의 화면: 답을 다 받은 뒤의 대화를 탭에 남겨 새로고침해도 이어지게 합니다.
  useEffect(() => {
    if (isStreaming || isServerSession(state.sessionId)) return;
    saveMockChat(state.sessionId, state);
  }, [state, isStreaming]);

  const history = useChatHistory(session);
  const pendingAsk = session.entry.pending_ask;
  useEffect(() => {
    if (history.data?.length) dispatch({ type: 'restore', messages: history.data, pendingAsk });
  }, [history.data, pendingAsk]);
  // 이전 대화를 못 받으면 대화가 없던 것처럼 보이지 않게 서버 문구를 말풍선으로 알립니다.
  useEffect(() => {
    if (!history.error) return;
    dispatch({
      type: 'system',
      text:
        history.error instanceof ApiError
          ? history.error.message
          : '이전 대화를 불러오지 못했어요. 새로고침해 주세요.',
    });
  }, [history.error]);

  useEffect(() => () => abortRef.current?.abort(), [sessionId]);

  /** 업로드 실패처럼 스트림 밖에서 생긴 오류를 말풍선으로 보여 줍니다. */
  const notifySystem = useCallback((text: string) => dispatch({ type: 'system', text }), []);

  const send = useCallback(
    async (text: string, options: SendOptions = {}) => {
      const { inputKind = 'text', fileIds, attachments, importIds } = options;
      const message = text.trim();
      if (!message || abortRef.current) return;

      const controller = new AbortController();
      abortRef.current = controller;
      dispatch({ type: 'user_sent', text: message, inputKind, attachments });
      setInputText('');
      setIsStreaming(true);

      try {
        const stream = await streamChat(
          sessionId,
          { message, input_kind: inputKind, file_ids: fileIds, import_ids: importIds },
          controller.signal,
        );
        for await (const event of stream) {
          if (controller.signal.aborted) break;
          switch (event.event) {
            case 'token':
              dispatch({ type: 'token', text: event.data.text });
              break;
            case 'tool_call':
              setActiveTool(event.data.status === 'started' ? event.data.name : null);
              break;
            case 'ask_user':
              dispatch({
                type: 'ask_user',
                text: event.data.text,
                choices: event.data.choices,
                importKind: event.data.import_kind,
                acceptsFile: event.data.accepts_file,
              });
              break;
            case 'form_update':
              applyFormUpdateEvent(event.data);
              break;
            case 'done':
              dispatch({ type: 'done', cite: event.data.cite });
              break;
            case 'error': {
              const described = describeChatError(event.data);
              dispatch({ type: 'system', text: described.text });
              if (described.restoresInput) setInputText(message);
              break;
            }
          }
        }
      } catch {
        if (!controller.signal.aborted) {
          dispatch({ type: 'system', text: describeChatError({ code: 'LLM_UNAVAILABLE' }).text });
          setInputText(message);
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setActiveTool(null);
        setIsStreaming(false);
      }
    },
    [sessionId],
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
