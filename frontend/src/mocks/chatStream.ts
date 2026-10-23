import { getSession } from '@/lib/sessionStore';
import { SSE_EVENTS } from '@/lib/sseEvents';
import type { MessageCreate, SseMessage } from '@/types/chat.types';

import { buildMockChatEvents } from './chatScripts';
import { MOCK_ENTRIES } from './entries';

const TOKEN_DELAY_MS = 25;
const TOOL_DELAY_MS = 300;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** 스크립트 이벤트를 실제 스트림처럼 조금씩 흘려 보냅니다. */
export async function* mockChatStream(
  personaId: string,
  body: MessageCreate,
  signal?: AbortSignal,
): AsyncGenerator<SseMessage> {
  // 이력서 저장처럼 단계가 바뀌면 진입 결과도 바뀌므로 지금 세션의 첫 선택지를 씁니다 (모의 자유 입력).
  const session = getSession();
  const entryChoices =
    (session?.persona_id === personaId ? session.entry.choices : undefined) ??
    MOCK_ENTRIES[personaId]?.choices ??
    [];
  const events = buildMockChatEvents(
    personaId,
    body.text,
    entryChoices,
    body.file_ids,
    body.import_ids,
  );

  await wait(TOOL_DELAY_MS);
  for (const event of events) {
    if (signal?.aborted) return;
    yield event;
    await wait(event.event === SSE_EVENTS.TOOL_CALL ? TOOL_DELAY_MS : TOKEN_DELAY_MS);
  }
}
