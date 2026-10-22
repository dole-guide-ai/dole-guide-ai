import { API_PATHS } from '@/lib/apiPaths';
import { usesMock } from '@/lib/mockMode';
import { openSseStream, type RawSseEvent } from '@/lib/sse';
import type { ChatCreate, SseMessage } from '@/types/chat.types';
import { mockChatStream } from '@/mocks/chatStream';

const toMessage = ({ event, data }: RawSseEvent): SseMessage =>
  ({ event, data: data ? JSON.parse(data) : {} }) as SseMessage;

async function* toMessages(events: AsyncIterable<RawSseEvent>): AsyncGenerator<SseMessage> {
  for await (const event of events) yield toMessage(event);
}

/**
 * `POST /accounts/{persona_id}/messages` → SSE (대화 턴 하나). 모의 모드면 스크립트 이벤트를 흘려 보냅니다.
 * 턴 시작 전 실패(409 TURN_IN_PROGRESS 등)는 `ApiError`로 던집니다.
 */
export const streamChat = async (
  personaId: string,
  sessionId: string,
  body: ChatCreate,
  signal?: AbortSignal,
): Promise<AsyncIterable<SseMessage>> => {
  const path = API_PATHS.messages(personaId);
  if (usesMock(path)) return mockChatStream(sessionId, body, signal);

  const events = await openSseStream(path, {
    method: 'POST',
    body: JSON.stringify({
      text: body.message,
      input_kind: body.input_kind,
      file_ids: body.file_ids ?? [],
      import_ids: body.import_ids ?? [],
    }),
    signal,
  });
  return toMessages(events);
};
