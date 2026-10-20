import type { SseMessage } from '@/types/chat.types';

/** SSE 이벤트 배열을 `text/event-stream` 본문으로 직렬화합니다. */
export const toSseText = (events: SseMessage[]) =>
  events.map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join('');

/** 글자를 여러 덩어리로 잘라 보내는 스트림 응답. 이벤트 경계와 덩어리 경계가 어긋나도 읽히는지 확인용. */
export const sseResponse = (events: SseMessage[], chunkSize = 7) => {
  const text = toSseText(events);
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < text.length; i += chunkSize) {
        controller.enqueue(encoder.encode(text.slice(i, i + chunkSize)));
      }
      controller.close();
    },
  });
  return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
};
