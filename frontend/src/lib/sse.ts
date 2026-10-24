import { API_BASE_URL, ApiError, networkError, toApiError } from '@/lib/api';
import { ERROR_CODES } from '@/lib/errorCodes';

export interface RawSseEvent {
  event: string;
  data: string;
}

/**
 * POST로 SSE를 열고 이벤트 스트림을 돌려줍니다. 대화는 POST라 EventSource를 못 써서 여기서 fetch합니다.
 * 실패는 `apiFetch`와 같은 ApiError로 통일합니다.
 */
export const openSseStream = async (
  path: string,
  init?: RequestInit,
): Promise<AsyncGenerator<RawSseEvent>> => {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        ...init?.headers,
      },
    });
  } catch {
    throw networkError();
  }
  if (!res.ok) throw await toApiError(res);
  if (!res.body) throw new ApiError(ERROR_CODES.INTERNAL_ERROR, '응답 본문이 없어요.', res.status);
  return parseSseStream(res.body);
};

/**
 * SSE 본문을 이벤트 단위로 나눕니다. `event:`·`data:` 줄을 모으고 빈 줄에서 하나를 내보냅니다.
 * 대화는 POST라 EventSource를 못 써서 fetch 본문을 직접 읽습니다 (2-0.11).
 */
export async function* parseSseStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<RawSseEvent> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary = findBoundary(buffer);
      while (boundary) {
        const block = buffer.slice(0, boundary.index);
        buffer = buffer.slice(boundary.index + boundary.length);
        const event = parseSseBlock(block);
        if (event) yield event;
        boundary = findBoundary(buffer);
      }
    }
    const tail = parseSseBlock(buffer + decoder.decode());
    if (tail) yield tail;
  } finally {
    reader.releaseLock();
  }
}

const findBoundary = (text: string) => {
  const match = /\r?\n\r?\n/.exec(text);
  return match ? { index: match.index, length: match[0].length } : null;
};

/** 빈 줄로 끝나는 블록 하나를 이벤트로 바꿉니다. 이벤트 이름이 없으면 `message`입니다. */
export const parseSseBlock = (block: string): RawSseEvent | null => {
  let event = 'message';
  const dataLines: string[] = [];

  for (const rawLine of block.split(/\r?\n/)) {
    if (!rawLine || rawLine.startsWith(':')) continue;
    const colon = rawLine.indexOf(':');
    const field = colon === -1 ? rawLine : rawLine.slice(0, colon);
    let value = colon === -1 ? '' : rawLine.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);

    if (field === 'event') event = value;
    else if (field === 'data') dataLines.push(value);
  }

  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join('\n') };
};
