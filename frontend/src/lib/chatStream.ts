import { API_PATHS } from '@/lib/apiPaths';
import { IDEMPOTENCY_HEADER, newIdempotencyKey } from '@/lib/idempotency';
import { openSseStream, type RawSseEvent } from '@/lib/sse';
import type { MessageCreate, SseMessage } from '@/types/chat.types';

const toMessage = ({ event, data }: RawSseEvent): SseMessage =>
  ({ event, data: data ? JSON.parse(data) : {} }) as SseMessage;

async function* toMessages(events: AsyncIterable<RawSseEvent>): AsyncGenerator<SseMessage> {
  for await (const event of events) yield toMessage(event);
}

/**
 * `POST /accounts/{persona_id}/messages` → SSE (대화 턴 하나).
 * 턴 시작 전 실패(409 TURN_IN_PROGRESS 등)는 `ApiError`로 던집니다.
 * `idempotencyKey`: 같은 전송이 두 번 가도 턴이 한 번만 돌게 하는 키. 같은 키가 다시 가면 409입니다.
 */
export const streamChat = async (
  personaId: string,
  body: MessageCreate,
  signal?: AbortSignal,
  idempotencyKey: string = newIdempotencyKey(),
): Promise<AsyncIterable<SseMessage>> => {
  const path = API_PATHS.messages(personaId);
  const events = await openSseStream(path, {
    method: 'POST',
    headers: { [IDEMPOTENCY_HEADER]: idempotencyKey },
    body: JSON.stringify(body),
    signal,
  });
  return toMessages(events);
};
