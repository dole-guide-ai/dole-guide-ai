import { usesMock } from '@/lib/api';
import { openSseStream, type RawSseEvent } from '@/lib/sse';
import type { ChatCreate, SseMessage } from '@/types/chat.types';
import { mockChatStream } from '@/mocks/chatStream';

const toMessage = ({ event, data }: RawSseEvent): SseMessage =>
  ({ event, data: data ? JSON.parse(data) : {} }) as SseMessage;

async function* toMessages(events: AsyncIterable<RawSseEvent>): AsyncGenerator<SseMessage> {
  for await (const event of events) yield toMessage(event);
}

/** `POST /sessions/{session_id}/chat` → SSE (2-0.11). 모의 모드면 스크립트 이벤트를 흘려 보냅니다. */
export const streamChat = async (
  sessionId: string,
  body: ChatCreate,
  signal?: AbortSignal,
): Promise<AsyncIterable<SseMessage>> => {
  const path = `/sessions/${sessionId}/chat`;
  if (usesMock(path)) return mockChatStream(sessionId, body, signal);

  const events = await openSseStream(path, {
    method: 'POST',
    body: JSON.stringify(body),
    signal,
  });
  return toMessages(events);
};
