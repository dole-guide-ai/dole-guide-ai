import sseEvents from '../../../shared/sse-events.json';

export const SSE_EVENTS = sseEvents;

export type SseEventName = (typeof SSE_EVENTS)[keyof typeof SSE_EVENTS];

export interface RawSseEvent {
  event: string;
  data: string;
}

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
