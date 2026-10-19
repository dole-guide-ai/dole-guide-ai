import { API_BASE_URL, IS_MOCK_API } from '@/lib/api';
import { ApiError } from '@/lib/apiError';
import { parseSseStream, type RawSseEvent } from '@/lib/sse';
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
  if (IS_MOCK_API) return mockChatStream(sessionId, body, signal);

  const path = `/sessions/${sessionId}/chat`;
  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new ApiError(res.status, path);
  if (!res.body) throw new ApiError(res.status, path, '응답 본문이 없어요.');
  return toMessages(parseSseStream(res.body));
};
