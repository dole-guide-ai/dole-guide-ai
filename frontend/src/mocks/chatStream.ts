import type { ChatCreate, SseMessage } from '@/types/chat.types';

import { buildMockChatEvents } from './chatScripts';
import { MOCK_ENTRIES } from './entries';

const TOKEN_DELAY_MS = 25;
const TOOL_DELAY_MS = 300;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** 모의 세션 ID는 `mock-{persona_id}-{time}` 형태입니다 (handlers.buildMockSession). */
const personaFromSession = (sessionId: string) => sessionId.split('-')[1] ?? '';

/** 스크립트 이벤트를 실제 스트림처럼 조금씩 흘려 보냅니다. */
export async function* mockChatStream(
  sessionId: string,
  body: ChatCreate,
  signal?: AbortSignal,
): AsyncGenerator<SseMessage> {
  const personaId = personaFromSession(sessionId);
  const entryChoices = MOCK_ENTRIES[personaId]?.choices ?? [];
  const events = buildMockChatEvents(
    personaId,
    body.message,
    entryChoices,
    body.file_ids,
    body.import_ids,
  );

  await wait(TOOL_DELAY_MS);
  for (const event of events) {
    if (signal?.aborted) return;
    yield event;
    await wait(event.event === 'tool_call' ? TOOL_DELAY_MS : TOKEN_DELAY_MS);
  }
}
