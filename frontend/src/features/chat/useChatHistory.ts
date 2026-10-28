import { useQuery } from '@tanstack/react-query';

import type { ChatMessage, ChatRole } from '@/features/chat/chat.types';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { queryKeys } from '@/lib/queryKeys';
import { SSE_EVENTS } from '@/lib/sseEvents';
import type { components } from '@/types/api.gen';
import type { ChatInputKind } from '@/types/chat.types';
import type { EntryResult, SessionRead } from '@/types/demo.types';
import type { ImportKind } from '@/types/imports.types';

type MessageList = components['schemas']['MessageList'];
type MessageRead = components['schemas']['MessageRead'];

const ROLES: ChatRole[] = ['assistant', 'user', 'system'];

/** 서버에 저장된 말풍선 하나를 화면 말풍선으로 바꿉니다. 근거 줄·입력 방식은 payload에 있습니다. */
export const toChatMessage = (message: MessageRead): ChatMessage => {
  const payload = message.payload ?? {};
  return {
    id: `h-${message.seq}`,
    role: ROLES.includes(message.role as ChatRole) ? (message.role as ChatRole) : 'assistant',
    text: message.text ?? '',
    ...(typeof payload.cite === 'string' ? { cite: payload.cite } : {}),
    ...(typeof payload.input_kind === 'string'
      ? { inputKind: payload.input_kind as ChatInputKind }
      : {}),
  };
};

/**
 * 마지막 말풍선이 질문(ask_user)이면 아직 답하지 않은 질문입니다(서버 `pending_ask`와 같은 규칙).
 * 로그인 때 저장한 세션의 pending_ask는 그 뒤 대화를 모르므로 기록에서 다시 구합니다.
 */
export const pendingAskOf = (messages: MessageRead[]): EntryResult['pending_ask'] => {
  const last = messages.at(-1);
  if (!last || last.kind !== SSE_EVENTS.ASK_USER || !last.payload) return null;
  const {
    choices,
    import_kind: importKind,
    accepts_file: acceptsFile,
    file_choice: fileChoice,
  } = last.payload;
  return {
    choices: Array.isArray(choices) ? choices.filter((c) => typeof c === 'string') : [],
    import_kind: typeof importKind === 'string' ? (importKind as ImportKind) : null,
    accepts_file: acceptsFile === true,
    file_choice: typeof fileChoice === 'string' ? fileChoice : null,
  };
};

/** 저장된 대화를 처음부터 끝까지 받습니다(한 번에 100개씩, next_cursor로 이어 받기). */
const fetchAll = async (personaId: string) => {
  const items: MessageRead[] = [];
  let cursor: number | null | undefined = 0;
  while (cursor !== null && cursor !== undefined) {
    const query: string = cursor ? `?cursor=${cursor}` : '';
    const page: MessageList = await apiFetch<MessageList>(
      `${API_PATHS.messages(personaId)}${query}`,
    );
    items.push(...page.items);
    cursor = page.next_cursor;
  }
  return { messages: items.map(toChatMessage), pendingAsk: pendingAskOf(items) };
};

/**
 * 새로고침해도 대화가 그대로 보이게 서버 대화 기록(`GET /accounts/{id}/messages`)을 받습니다 (F-03).
 */
export const useChatHistory = (session: SessionRead) =>
  useQuery({
    queryKey: queryKeys.messages(session.session_id),
    queryFn: () => fetchAll(session.persona_id),
    // 다시 입장(방문자 토큰이 바뀔 수 있음)하면 캐시를 쓰지 않고 새로 받습니다.
    gcTime: 0,
    refetchOnWindowFocus: false,
  });
