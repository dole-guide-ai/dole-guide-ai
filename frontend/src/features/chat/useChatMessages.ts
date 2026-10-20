import { useCallback, useRef, useState } from 'react';

import type { ChatInputKind, ChatMessage } from '@/features/chat/chat.types';

import type { SessionRead } from '@/types/demo.types';

interface ChatState {
  sessionId: string;
  messages: ChatMessage[];
  choices: string[];
}

const fromSession = (session: SessionRead): ChatState => ({
  sessionId: session.session_id,
  messages: session.entry.messages.map((message, index) => ({
    id: `entry-${index}`,
    role: 'assistant',
    text: message.text,
    cite: message.cite,
  })),
  choices: session.entry.choices,
});

/**
 * 말풍선 목록과 현재 선택지. 첫 안내(진입 결과)로 시작하고, 세션이 바뀌면 처음부터 다시 만듭니다.
 * SSE 스트림(`token`·`ask_user`)으로 이어 붙이는 일은 다음 단계(2-0)에서 더합니다.
 */
export const useChatMessages = (session: SessionRead) => {
  const [state, setState] = useState<ChatState>(() => fromSession(session));
  const nextIdRef = useRef(0);

  if (state.sessionId !== session.session_id) {
    setState(fromSession(session));
  }

  const sendUserMessage = useCallback((text: string, inputKind: ChatInputKind = 'text') => {
    const trimmed = text.trim();
    if (!trimmed) return;
    nextIdRef.current += 1;
    const message: ChatMessage = {
      id: `user-${nextIdRef.current}`,
      role: 'user',
      text: trimmed,
      inputKind,
    };
    setState((prev) => ({ ...prev, messages: [...prev.messages, message], choices: [] }));
  }, []);

  return { messages: state.messages, choices: state.choices, sendUserMessage };
};
